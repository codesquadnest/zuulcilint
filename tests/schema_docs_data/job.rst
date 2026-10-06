.. _job:

Job
===

A job is a unit of work.

.. attr:: job

   The following attributes are available on a job; all are optional
   unless otherwise specified:

   .. attr:: name
      :required:

      The name of the job.  By default, Zuul looks for a playbook with
      this name.  See :ref:`global_repo_state` and
      :ref:`the docs <global_repo_state>`.

   .. TODO: figure out how to link the parent default

   .. attr:: abstract
      :default: false
      :type: bool

      To indicate a job is not intended to be run directly, set this
      to :value:`true`.

      Once this is set it cannot be reset; see :attr:`job.final` for
      ``more``, *emphasis* and **strong** text.

   .. attr:: files

      A list of regular expressions.  Examples:

      * first item
        continued here
      * second item

      Usage::

         files: foo

      .. code-block:: yaml

         - job:
             name: x

      .. warning:: This is risky
                   and wraps.

      .. note:: Be aware.

   .. attr:: nodeset

      The nodeset to use.

      .. attr:: nodes

         The nodes.

         .. attr:: name
            :required:

            The node name.

      The tail of nodeset.

   .. attr:: ansible-version

      The version.

      .. value:: 9

         Supported.

      .. value:: 11

.. _global_repo_state:

Global Repo State
-----------------

Text.
