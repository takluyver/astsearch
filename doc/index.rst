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

.. option:: -m MAX_LINES, --max-lines MAX_LINES

   By default, on Python >=3.8, multiline matches are fully printed, up to a
   maximum of 10 lines.  This maximum number of printed lines can be set by
   this option.  Setting it to 0 disables multiline printing.

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

