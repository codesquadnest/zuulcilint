"""Tests for the schema description updater script."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest
from jsonschema import Draft201909Validator

from scripts import update_schema_descriptions as usd

DATA = Path(__file__).parent / "schema_docs_data"
EXIT_ERROR = 2
REAL_SCHEMA = Path(usd.DEFAULT_SCHEMA)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Fail loudly if any test tries to reach the network."""

    def _boom(*_args, **_kwargs):
        msg = "network access is not allowed in tests"
        raise AssertionError(msg)

    monkeypatch.setattr(urllib.request, "urlopen", _boom)


@pytest.fixture(autouse=True)
def _fixture_doc_files(monkeypatch):
    """Only the cut-down fixture documents exist locally."""
    monkeypatch.setattr(usd, "DOC_FILES", ("job.rst", "gerrit.rst"))


@pytest.fixture
def mini_schema(tmp_path):
    """Copy the mini schema into a temporary location."""
    path = tmp_path / "schema.json"
    path.write_text((DATA / "mini-schema.json").read_text(encoding="utf-8"), encoding="utf-8")
    return path


@pytest.fixture
def attrs():
    """Attributes parsed from the fixture docs."""
    result = {}
    for name in ("job.rst", "gerrit.rst"):
        result.update(usd.parse_attrs((DATA / name).read_text(encoding="utf-8")))
    return result


def test_parse_attrs_paths_and_bodies(attrs):
    """Nested attrs get dotted paths and do not leak into the parent body."""
    assert attrs["job.name"].startswith("The name of the job. By default")
    assert "required" not in attrs["job.name"]
    assert attrs["job.nodeset"] == "The nodeset to use.\n\nThe tail of nodeset."
    assert attrs["job.nodeset.nodes"] == "The nodes."
    assert attrs["job.nodeset.nodes.name"] == "The node name."
    assert attrs["<gerrit connection>.server"].startswith("Fully qualified")
    assert "pipeline.reporter.<gerrit reporter>.submit" in attrs


def test_parse_attrs_options_and_comments_excluded(attrs):
    """Option lines and RST comments never end up in descriptions."""
    for text in attrs.values():
        assert ":default:" not in text
        assert ":type:" not in text
        assert "TODO" not in text


def test_parse_attrs_values_lists_and_admonitions(attrs):
    """Values stay as paragraphs, bullets as dashes, admonitions get a prefix."""
    assert attrs["job.ansible-version"] == "The version.\n\n9: Supported.\n\n11"
    files = attrs["job.files"]
    assert "- first item continued here\n- second item" in files
    assert "Warning: This is risky and wraps." in files
    assert "Note: Be aware." in files
    assert "name: x" not in files
    assert "files: foo" not in files
    assert "Usage" not in files


def test_parse_attrs_label_resolution(attrs):
    """``:ref:`` resolves to the section title or to the explicit text."""
    assert attrs["job.name"].endswith("See Global Repo State and the docs.")


def test_parse_attrs_crlf():
    """Windows line endings are normalized."""
    rst = ".. attr:: job.x\r\n\r\n   Hello\r\n   world.\r\n"
    assert usd.parse_attrs(rst) == {"job.x": "Hello world."}


def test_parse_attrs_first_duplicate_wins():
    """When a path is documented twice the first definition is kept."""
    rst = ".. attr:: a\n\n   one\n\n.. attr:: a\n\n   two\n"
    assert usd.parse_attrs(rst) == {"a": "one"}


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (":attr:`job.final`", "job.final"),
        (":value:`true`", "true"),
        (":var:`zuul.project`", "zuul.project"),
        (":term:`config-project`", "config-project"),
        (":attr:`the final <job.final>`", "the final"),
        (":ref:`some_label`", "some_label"),
        (":ref:`Some text <some_label>`", "Some text"),
        ("``literal`` text", "literal text"),
        ("*emph* and **strong**", "emph and strong"),
        ("`default role`", "default role"),
        ("`site <https://example.org>`_", "site (https://example.org)"),
        ("a\n   wrapped\n line", "a wrapped line"),
        ("2 * 3 and 4 * 5", "2 * 3 and 4 * 5"),
        ("escaped \\* star", "escaped * star"),
    ],
)
def test_rst_to_text(source, expected):
    """Inline markup is converted to plain text."""
    assert usd.rst_to_text(source) == expected


def test_rst_to_text_uses_labels():
    """Labels map to their section titles."""
    assert usd.rst_to_text(":ref:`lbl`", {"lbl": "Title"}) == "Title"


def test_collect_labels():
    """Labels are mapped to the section title that follows them."""
    rst = ".. _foo:\n\nMy Title\n--------\n\n.. _bar:\n\nplain paragraph\n"
    assert usd.collect_labels(rst) == {"foo": "My Title"}


def test_normalize_title():
    """Titles are unescaped, cleaned and aliased."""
    assert usd.normalize_title("job.&lt;x&gt;") == "job.<x>"
    assert usd.normalize_title("  job.name § ") == "job.name"
    assert (
        usd.normalize_title("pipeline.&lt;reporter&gt;.&lt;gerrit source&gt;.submit")
        == "pipeline.reporter.<gerrit reporter>.submit"
    )
    timer = usd.normalize_title("pipeline.trigger.&lt;timere&gt;.time")
    assert timer == "pipeline.trigger.timer.time"


def test_plan_and_apply_updates(mini_schema, attrs):
    """Only matched, changed descriptions are replaced; everything else is byte-identical."""
    text = mini_schema.read_text(encoding="utf-8")
    updates, unmatched = usd.plan_updates(text, attrs)
    assert {u.title for u in updates} == {
        "job.name",
        "job.abstract",
        "job.files",
        "pipeline.&lt;reporter&gt;.&lt;gerrit source&gt;.submit",
    }
    assert "job.description" in unmatched
    new = usd.apply_updates(text, updates)
    assert new != text
    data = json.loads(new)
    props = data["definitions"]["job"]["properties"]
    assert props["name"]["description"] == attrs["job.name"]
    assert props["description"]["description"] == "keep me: no docs match"
    assert props["nodeset"]["description"] == "no title so untouched"
    # Inline arrays and non-ASCII characters outside the changed spans are preserved.
    assert '"enum": ["a", "b"],' in new
    assert '"type": ["string", "array"],' in new
    assert "keep me: no docs match" in new
    Draft201909Validator.check_schema(data)
    # Idempotent.
    again, _ = usd.plan_updates(new, attrs)
    assert again == []
    assert usd.apply_updates(new, again) == new


def test_apply_updates_preserves_unchanged_bytes(mini_schema):
    """A description that does not change keeps its original bytes (curly quotes)."""
    text = mini_schema.read_text(encoding="utf-8")
    attrs = {"job.abstract": "Don\u2019t touch \u2019this\u2019 until changed."}
    updates, _ = usd.plan_updates(text, attrs)
    assert updates == []
    assert usd.apply_updates(text, updates) == text


def test_description_property_object_ignored():
    """A property called ``description`` with an object value is not a description string."""
    text = (
        '{"properties": {"description": {"title": "x.description", "description": "old"}},'
        ' "description": "top"}'
    )
    updates, _ = usd.plan_updates(text, {"x.description": "new"})
    assert len(updates) == 1
    out = usd.apply_updates(text, updates)
    assert json.loads(out) == {
        "properties": {"description": {"title": "x.description", "description": "new"}},
        "description": "top",
    }


def test_apply_updates_count_mismatch_fails(monkeypatch):
    """A mismatch between regex spans and parsed values is a loud error."""
    monkeypatch.setattr(usd, "_described_nodes", lambda _text: [])
    with pytest.raises(usd.UpdateError):
        usd.apply_updates('{"description": "x"}', [])


def test_only_filter(mini_schema, attrs):
    """``only`` restricts updates to a title prefix."""
    text = mini_schema.read_text(encoding="utf-8")
    updates, _ = usd.plan_updates(text, attrs, only="job.name")
    assert [u.title for u in updates] == ["job.name"]


def test_schema_zuul_ref(mini_schema):
    """The Zuul version is read from the schema title."""
    assert usd.schema_zuul_ref(mini_schema.read_text(encoding="utf-8")) == "1.2.3"
    with pytest.raises(usd.UpdateError):
        usd.schema_zuul_ref('{"title": "nope"}')


def test_real_schema_no_attrs_is_identity():
    """With no docs at all the real schema must round-trip byte for byte."""
    text = REAL_SCHEMA.read_text(encoding="utf-8")
    updates, unmatched = usd.plan_updates(text, {})
    assert updates == []
    assert unmatched
    assert usd.apply_updates(text, updates) == text


def test_cli_dry_run_and_report(mini_schema, capsys):
    """``--dry-run`` prints a diff and leaves the file alone."""
    before = mini_schema.read_text(encoding="utf-8")
    rc = usd.main(["--schema", str(mini_schema), "--docs-dir", str(DATA), "--dry-run", "--report"])
    out = capsys.readouterr().out
    assert rc == 0
    assert mini_schema.read_text(encoding="utf-8") == before
    assert "+++" in out
    assert "Schema titles without a docs match" in out
    assert "job.description" in out
    assert "Doc attrs missing from the schema" in out


def test_cli_check_and_write(mini_schema, capsys):
    """``--check`` exits 1 when outdated; a plain run writes and then ``--check`` passes."""
    base = ["--schema", str(mini_schema), "--docs-dir", str(DATA)]
    before = mini_schema.read_text(encoding="utf-8")
    assert usd.main([*base, "--check"]) == 1
    assert mini_schema.read_text(encoding="utf-8") == before
    assert usd.main(base) == 0
    assert mini_schema.read_text(encoding="utf-8") != before
    capsys.readouterr()
    assert usd.main([*base, "--check"]) == 0


def test_cli_errors_exit_2(mini_schema, tmp_path):
    """Missing docs or schema give exit status 2."""
    assert usd.main(["--schema", str(mini_schema), "--docs-dir", str(tmp_path)]) == EXIT_ERROR
    missing = str(tmp_path / "missing.json")
    assert usd.main(["--schema", missing, "--docs-dir", str(DATA)]) == EXIT_ERROR


def test_fetch_uses_pinned_url(monkeypatch):
    """Network fetches go through urllib with a tag-pinned opendev URL."""
    seen = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def read(self):
            return b"hello"

    def fake(url, timeout):
        seen.append((url, timeout))
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert usd.load_doc("1.2.3", "config/job.rst", None) == "hello"
    assert seen[0][0] == "https://opendev.org/zuul/zuul/raw/tag/1.2.3/doc/source/config/job.rst"
