"""Update ``description`` values in ``zuulcilint/zuul-schema.json`` from the Zuul docs.

This is a developer tool (it is not shipped in the wheel).  It fetches the Zuul
reStructuredText documentation for a given Zuul release, extracts the text of every
``.. attr::`` directive and rewrites the ``description`` of the schema node whose ``title``
is the matching Zuul attribute path (for example ``job.allowed-projects``).

Schema nodes without a title, or whose title has no counterpart in the docs, are left
untouched.  The schema file is rewritten span by span so that every byte outside the
replaced ``description`` strings (formatting, inline arrays, non-ASCII characters) is
preserved.

Only plain text output is produced.  Converting the descriptions to Markdown is possible
future work.

Examples:
    python -m scripts.update_schema_descriptions --dry-run --report
    python -m scripts.update_schema_descriptions --check
    python -m scripts.update_schema_descriptions --docs-dir ~/src/zuul --zuul-ref 11.2.0

Exit status: 0 on success, 1 if ``--check`` finds outdated descriptions, 2 on errors.

"""

from __future__ import annotations

import argparse
import difflib
import html
import json
import re
import sys
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SCHEMA = Path(__file__).resolve().parent.parent / "zuulcilint" / "zuul-schema.json"
DOC_URL = "https://opendev.org/zuul/zuul/raw/tag/{ref}/doc/source/{path}"
DOC_FILES = (
    "config/job.rst",
    "config/pipeline.rst",
    "config/project.rst",
    "config/nodeset.rst",
    "config/pragma.rst",
    "config/queue.rst",
    "config/secret.rst",
    "config/semaphore.rst",
    "drivers/gerrit.rst",
    "drivers/github.rst",
    "drivers/zuul.rst",
    "drivers/timer.rst",
    "drivers/mqtt.rst",
)
FETCH_TIMEOUT = 30

# Schema title prefix -> documentation attribute path prefix, for naming differences.
ALIASES: dict[str, str] = {
    "pipeline.trigger.<zuul source>": "pipeline.trigger.zuul",
    "pipeline.trigger.<timer>": "pipeline.trigger.timer",
    "pipeline.trigger.<timer source>": "pipeline.trigger.timer",
    "pipeline.trigger.<timere>": "pipeline.trigger.timer",
    "pipeline.<reporter>.<gerrit source>": "pipeline.reporter.<gerrit reporter>",
    "pipeline.<reporter>.<mqtt source>": "pipeline.<reporter>.<mqtt>",
}

DROPPED_DIRECTIVES = {"code-block", "literalinclude", "program-output", "toctree", "code", "todo"}
ADMONITIONS = {"warning": "Warning", "note": "Note"}


class UpdateError(Exception):

    """Raised when the docs cannot be parsed or the schema cannot be rewritten safely."""


@dataclass(frozen=True)
class Update:

    """A planned change of one schema description."""

    title: str
    old: str
    new: str
    index: int


# --------------------------------------------------------------------------------------
# RST parsing
# --------------------------------------------------------------------------------------

_DIRECTIVE_RE = re.compile(r"^(?P<indent>\s*)\.\. (?P<name>[\w-]+)::[ \t]*(?P<arg>.*)$")
_COMMENT_RE = re.compile(r"^(?P<indent>\s*)\.\.(?:\s.*)?$")
_LABEL_RE = re.compile(r"^\.\. _(?P<label>[^:]+):\s*$")
_OPTION_RE = re.compile(r"^\s+:[\w-]+:(?:\s.*)?$")
_BULLET_RE = re.compile(r"^(?P<indent>\s*)(?:[*+•-]|\d+\.|#\.)\s+(?P<text>.*)$")
_UNDERLINE_RE = re.compile(r"^([=\-~^\"#*+`:.'_])\1{2,}\s*$")


def _indent(line: str) -> int:
    """Return the indentation width of a line."""
    return len(line) - len(line.lstrip())


def normalize_title(title: str) -> str:
    """Normalize a schema title or attribute path so both sides can be compared."""
    text = html.unescape(title).replace("§", "")
    text = re.sub(r"\s+", " ", text).strip()
    for prefix, target in ALIASES.items():
        if text == prefix or text.startswith(prefix + "."):
            return target + text[len(prefix) :]
    return text


def collect_labels(text: str) -> dict[str, str]:
    """Map RST labels (``.. _name:``) to the title of the section that follows them."""
    labels: dict[str, str] = {}
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        match = _LABEL_RE.match(line)
        if not match:
            continue
        nxt = idx + 1
        while nxt < len(lines) and not lines[nxt].strip():
            nxt += 1
        title = lines[nxt].strip() if nxt < len(lines) else ""
        if (
            nxt + 1 < len(lines)
            and title
            and _UNDERLINE_RE.match(lines[nxt + 1])
            and not title.startswith("..")
        ):
            labels[match.group("label").strip().lower()] = title
    return labels


_ROLE_RE = re.compile(r":(?:[\w+-]+:)?[\w+-]+:`(?P<body>[^`]+)`")
_LINK_RE = re.compile(r"`(?P<text>[^`<]+?)\s*<(?P<url>[^>]+)>`__?")
_NAMED_REF_RE = re.compile(r"(?<![\w`])`(?P<t>[^`<>]+)`__?(?!\w)")
_LITERAL_RE = re.compile(r"``(?P<t>.+?)``")
_INTERPRETED_RE = re.compile(r"(?<![\w`])`(?P<t>[^`]+)`(?![\w`])")
_STRONG_RE = re.compile(r"(?<![\w*\\])\*\*(?=\S)(?P<t>.+?)(?<=\S)\*\*(?![\w*])")
_EM_RE = re.compile(r"(?<![\w*\\])\*(?=[^\s*])(?P<t>[^*\n]+?)(?<=[^\s*])\*(?![\w*])")
_TARGET_RE = re.compile(r"^(?P<text>.*?)\s*<(?P<target>[^<>]+)>$", re.DOTALL)


def _role_text(match: re.Match[str], labels: dict[str, str]) -> str:
    """Return the plain text of an inline role match."""
    role = match.group(0).split("`", 1)[0].strip(":").rsplit(":", 1)[-1]
    body = match.group("body")
    target = _TARGET_RE.match(body)
    if target:
        return target.group("text") or target.group("target")
    if role == "ref":
        return labels.get(body.strip().lower(), body)
    return body


def rst_to_text(text: str, labels: dict[str, str] | None = None) -> str:
    """Convert a single paragraph of inline RST markup to plain text."""
    labels = labels or {}
    out = re.sub(r"\s+", " ", text).strip()
    out = _ROLE_RE.sub(lambda m: _role_text(m, labels), out)
    out = _LINK_RE.sub(lambda m: f"{m.group('text')} ({m.group('url')})", out)
    out = _NAMED_REF_RE.sub(lambda m: m.group("t"), out)
    out = _LITERAL_RE.sub(lambda m: "\0" + m.group("t") + "\1", out)
    out = _INTERPRETED_RE.sub(lambda m: m.group("t"), out)
    out = _STRONG_RE.sub(lambda m: m.group("t"), out)
    out = _EM_RE.sub(lambda m: m.group("t"), out)
    out = out.replace("\0", "").replace("\1", "")
    return re.sub(r"\\(.)", r"\1", out)


def _consume_block(lines: list[str], start: int, indent: int) -> int:
    """Return the index just past the indented block following ``lines[start - 1]``."""
    idx = start
    last = start
    while idx < len(lines):
        line = lines[idx]
        if line.strip():
            if _indent(line) <= indent:
                break
            last = idx + 1
        idx += 1
    return last


def _split_options(block: list[str]) -> list[str]:
    """Drop the leading field-list options (``:required:`` etc.) from a directive block."""
    idx = 0
    while idx < len(block) and _OPTION_RE.match(block[idx]):
        idx += 1
    return block[idx:]


def _paragraph_blocks(lines: list[str], labels: dict[str, str]) -> list[tuple[str, str]]:
    """Turn raw text lines into ``(kind, text)`` blocks; kind is ``p`` or ``b`` (bullet)."""
    body = textwrap.dedent("\n".join(lines)).splitlines()
    chunks: list[list[str]] = []
    cur: list[str] = []
    for line in body:
        if line.strip():
            cur.append(line)
        elif cur:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)

    blocks: list[tuple[str, str]] = []
    literal = False
    for chunk in chunks:
        if literal and _indent(chunk[0]) > 0:
            _drop_dangling_intro(blocks)
            continue
        literal = False
        if _BULLET_RE.match(chunk[0]):
            blocks.extend(_bullet_items(chunk, labels))
            continue
        text = " ".join(part.strip() for part in chunk)
        if text.endswith("::"):
            literal = True
            text = text[:-1] if text[:-2].strip() and not text[:-2].endswith(" ") else text[:-2]
        plain = rst_to_text(text, labels)
        if plain:
            blocks.append(("p", plain))
    return blocks


def _drop_dangling_intro(blocks: list[tuple[str, str]]) -> None:
    """Remove a trailing ``Example:`` style paragraph whose code block was dropped."""
    if blocks and blocks[-1][0] == "p" and blocks[-1][1].endswith(":"):
        blocks.pop()


def _bullet_items(chunk: list[str], labels: dict[str, str]) -> list[tuple[str, str]]:
    """Split a chunk of consecutive bullet lines into one block per item."""
    items: list[list[str]] = []
    for line in chunk:
        match = _BULLET_RE.match(line)
        if match and (not items or _indent(line) <= _indent(chunk[0])):
            items.append([match.group("text")])
        elif items:
            items[-1].append(line.strip())
    return [("b", "- " + rst_to_text(" ".join(item), labels)) for item in items]


def _join_blocks(blocks: list[tuple[str, str]]) -> str:
    """Join blocks with blank lines, keeping consecutive bullets on adjacent lines."""
    out = ""
    prev = ""
    for kind, text in blocks:
        if out:
            out += "\n" if kind == "b" and prev == "b" else "\n\n"
        out += text
        prev = kind
    return out


def _parse_body(
    lines: list[str],
    path: str,
    labels: dict[str, str],
    attrs: dict[str, str],
) -> list[tuple[str, str]]:
    """Parse the body of a directive, registering nested ``attr`` blocks in ``attrs``."""
    blocks: list[tuple[str, str]] = []
    buf: list[str] = []
    idx = 0

    def flush() -> None:
        if buf:
            blocks.extend(_paragraph_blocks(buf, labels))
            buf.clear()

    while idx < len(lines):
        line = lines[idx]
        directive = _DIRECTIVE_RE.match(line)
        comment = None if directive else _COMMENT_RE.match(line)
        if not directive and not comment:
            buf.append(line)
            idx += 1
            continue
        flush()
        indent = len((directive or comment).group("indent"))  # type: ignore[union-attr]
        end = _consume_block(lines, idx + 1, indent)
        inner = _split_options(lines[idx + 1 : end])
        idx = end
        if comment:
            continue
        name = directive.group("name")  # type: ignore[union-attr]
        arg = directive.group("arg").strip()  # type: ignore[union-attr]
        if name == "attr":
            _register_attr(arg, inner, path, labels, attrs)
        elif name == "value":
            sub = _parse_body(inner, path, labels, attrs)
            first = f"{arg}: {sub[0][1]}" if sub else arg
            blocks.append(("p", first))
            blocks.extend(sub[1:])
        elif name in ADMONITIONS:
            sub = _parse_body([arg, *inner] if arg else inner, path, labels, attrs)
            if sub:
                blocks.append(("p", f"{ADMONITIONS[name]}: {_join_blocks(sub)}"))
        elif name in DROPPED_DIRECTIVES:
            _drop_dangling_intro(blocks)
    flush()
    return blocks


def _register_attr(
    arg: str,
    inner: list[str],
    parent: str,
    labels: dict[str, str],
    attrs: dict[str, str],
) -> None:
    """Record one ``.. attr::`` directive (and, recursively, its nested attrs)."""
    path = f"{parent}.{arg}" if parent else arg
    blocks = _parse_body(inner, path, labels, attrs)
    attrs.setdefault(path, _join_blocks(blocks))


def parse_attrs(rst: str, labels: dict[str, str] | None = None) -> dict[str, str]:
    """Parse an RST document and return ``{attr path: plain text description}``."""
    text = rst.replace("\r\n", "\n").replace("\r", "\n")
    all_labels = {**collect_labels(text), **(labels or {})}
    attrs: dict[str, str] = {}
    _parse_body(text.split("\n"), "", all_labels, attrs)
    return {normalize_title(path): desc for path, desc in attrs.items()}


# --------------------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------------------


def load_doc(zuul_ref: str, rel_path: str, docs_dir: Path | None) -> str:
    """Return the RST source for ``rel_path`` from a local checkout or from opendev."""
    if docs_dir is not None:
        base = docs_dir / "doc" / "source" if (docs_dir / "doc" / "source").is_dir() else docs_dir
        try:
            return (base / rel_path).read_text(encoding="utf-8")
        except OSError as exc:
            msg = f"cannot read {base / rel_path}: {exc}"
            raise UpdateError(msg) from exc
    url = DOC_URL.format(ref=zuul_ref, path=rel_path)
    try:
        with urllib.request.urlopen(url, timeout=FETCH_TIMEOUT) as resp:  # noqa: S310
            return resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError) as exc:
        msg = f"cannot fetch {url}: {exc}"
        raise UpdateError(msg) from exc


def load_attrs(zuul_ref: str, docs_dir: Path | None) -> dict[str, str]:
    """Load and parse all documentation files; return the merged attribute map."""
    texts = {rel: load_doc(zuul_ref, rel, docs_dir) for rel in DOC_FILES}
    labels: dict[str, str] = {}
    for text in texts.values():
        labels.update(collect_labels(text.replace("\r\n", "\n")))
    attrs: dict[str, str] = {}
    for text in texts.values():
        for key, value in parse_attrs(text, labels).items():
            attrs.setdefault(key, value)
    return attrs


# --------------------------------------------------------------------------------------
# Schema rewriting
# --------------------------------------------------------------------------------------

_DESC_SPAN_RE = re.compile(r'"description":\s*("(?:[^"\\]|\\.)*")')


class _Obj(list):

    """A JSON object kept as an ordered list of ``(key, value)`` pairs."""


def _described_nodes(text: str) -> list[tuple[str | None, str]]:
    """Return ``(title, description)`` for each string ``description``, in document order."""
    root = json.loads(text, object_pairs_hook=_Obj)
    found: list[tuple[str | None, str]] = []

    def walk(node: object) -> None:
        if isinstance(node, _Obj):
            title = next((v for k, v in node if k == "title" and isinstance(v, str)), None)
            for key, value in node:
                if key == "description" and isinstance(value, str):
                    found.append((title, value))
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(root)
    return found


def plan_updates(
    text: str,
    attrs: dict[str, str],
    only: str | None = None,
) -> tuple[list[Update], list[str]]:
    """Compute the description changes and the titles that have no documentation match."""
    nodes = _described_nodes(text)
    updates: list[Update] = []
    unmatched: list[str] = []
    for index, (title, old) in enumerate(nodes):
        if title is None:
            continue
        key = normalize_title(title)
        if key not in attrs:
            unmatched.append(title)
            continue
        new = attrs[key]
        if only and not key.startswith(only):
            continue
        if new and new != old:
            updates.append(Update(title, old, new, index))
    return updates, unmatched


def apply_updates(text: str, updates: list[Update]) -> str:
    """Return ``text`` with the described descriptions replaced; all else is untouched."""
    spans = list(_DESC_SPAN_RE.finditer(text))
    nodes = _described_nodes(text)
    if len(spans) != len(nodes):
        msg = f"found {len(spans)} description spans but {len(nodes)} description values"
        raise UpdateError(msg)
    for span, node in zip(spans, nodes):  # noqa: B905  # lengths checked above, py39 has no strict
        if json.loads(span.group(1)) != node[1]:
            msg = f"description span at offset {span.start(1)} does not match the parsed value"
            raise UpdateError(msg)
    out = text
    for upd in sorted(updates, key=lambda u: u.index, reverse=True):
        start, end = spans[upd.index].span(1)
        out = out[:start] + json.dumps(upd.new, ensure_ascii=False) + out[end:]
    return out


def verify_schema(text: str) -> None:
    """Check that the text is valid JSON and a valid draft 2019-09 JSON schema."""
    from jsonschema import Draft201909Validator  # noqa: PLC0415
    from jsonschema.exceptions import SchemaError  # noqa: PLC0415

    try:
        Draft201909Validator.check_schema(json.loads(text))
    except (ValueError, SchemaError) as exc:
        msg = f"rewritten schema is invalid: {exc}"
        raise UpdateError(msg) from exc


def schema_zuul_ref(text: str) -> str:
    """Extract the Zuul version from the schema title (``Zuul CI X.Y.Z``)."""
    title = json.loads(text).get("title", "")
    match = re.search(r"Zuul CI (\d+(?:\.\d+)+)", title)
    if not match:
        msg = f"cannot determine the Zuul version from the schema title {title!r}"
        raise UpdateError(msg)
    return match.group(1)


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def _titles(text: str) -> set[str]:
    """Return the normalized titles of all schema nodes that have a description."""
    return {normalize_title(t) for t, _ in _described_nodes(text) if t}


def build_parser() -> argparse.ArgumentParser:
    """Build the command line parser."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--zuul-ref", help="Zuul tag to read docs from (default: schema title)")
    parser.add_argument("--docs-dir", type=Path, help="local Zuul checkout (offline mode)")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="schema file")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="print diff, exit 1 if outdated")
    mode.add_argument("--dry-run", action="store_true", help="print diff, write nothing")
    parser.add_argument("--only", metavar="TITLE_PREFIX", help="only update matching titles")
    parser.add_argument("--report", action="store_true", help="report unmatched titles/attrs")
    return parser


def _run(args: argparse.Namespace) -> int:
    """Run the tool; raises UpdateError on failure."""
    try:
        text = args.schema.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"cannot read schema {args.schema}: {exc}"
        raise UpdateError(msg) from exc
    try:
        ref = args.zuul_ref or schema_zuul_ref(text)
        attrs = load_attrs(ref, args.docs_dir)
        updates, unmatched = plan_updates(text, attrs, args.only)
        new_text = apply_updates(text, updates)
        verify_schema(new_text)
    except ValueError as exc:
        raise UpdateError(str(exc)) from exc

    print(f"Zuul ref {ref}: {len(updates)} description(s) to update", file=sys.stderr)
    if args.check or args.dry_run:
        sys.stdout.writelines(
            difflib.unified_diff(
                text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=str(args.schema),
                tofile=f"{args.schema} (updated)",
            ),
        )
    if args.report:
        missing = sorted(set(attrs) - _titles(text))
        print(f"\nSchema titles without a docs match ({len(unmatched)}):")
        print("\n".join(f"  {html.unescape(t)}" for t in unmatched))
        print(f"\nDoc attrs missing from the schema ({len(missing)}):")
        print("\n".join(f"  {t}" for t in missing))
    if args.check:
        return 1 if updates else 0
    if not args.dry_run and updates:
        args.schema.write_text(new_text, encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = build_parser().parse_args(argv)
    try:
        return _run(args)
    except UpdateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
