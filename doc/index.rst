ASTsearch |version|
===================

ASTsearch is an intelligent search tool for Python code.

To get it::

    pip install astsearch

To use it::

    # astsearch pattern [path]
    astsearch "?/?"  # Division operations in all files in the current directory

.. program:: astsearch

.. option:: pattern

   A search pattern, using ``?`` as a wildcard to match anything. The pattern
   must be a valid Python statement once all ``?`` wilcards have been replaced
   with a name.

.. option:: path

   A Python file or a directory in which to search. Directories will be searched
   recursively for ``.py`` and ``.pyw`` files.

.. option:: -l, --files-with-matches

   Output only the paths of matching files, not the lines that matched.

Contents:

.. toctree::
   :maxdepth: 2

   api

.. seealso::

   `astpath <https://github.com/hchasestevens/astpath>`_
     Search through ASTs using XPath syntax

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

