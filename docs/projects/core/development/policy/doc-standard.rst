.. highlightlang:: rest

Sphinx Documentation Standard for Twisted
=========================================


.. contents::


Formatting
----------

Sphinx supports a huge variety of formatting and markup.
A small selection of the various markup constructs are touched upon below,
along with some stylistic specifications related to them.
For more information or a general overview of Sphinx, consult the
`reStructuredText primer <http://sphinx-doc.org/rest.html#restructuredtext-primer>`_
and other related documents in the official Sphinx documentation.


Headers
^^^^^^^

Sphinx documents do not mandate the use of any specific heirarchy of characters
when denoting header levels.

Twisted adopts the more-or-less standard heirarchy
used by the CPython and Sphinx documentation:

    * Use `=` (without overline) for section headings,
      which typically will be the highest level heading appearing in a document
    * Use `-` (without overline) for subsections
    * Use `^` (without overline) for subsubsections.

In long documents it may be convenient to adopt higher level headings.
See the `Sphinx documentation <http://sphinx-doc.org/rest.html#restructuredtext-primer>`_
for suggestions.


Spacing
^^^^^^^

Use two lines of spacing before a section heading (of any kind),
and one line of spacing afterwards.

One line of spacing should be left after a directive.


Code Blocks & Snippets
^^^^^^^^^^^^^^^^^^^^^^

Inline code snippets can be created by enclosing text with two backticks::

    This sentence contains an ``"important inlined string literal"``\ .

which renders as:

    This sentence contains an ``"important inlined string literal"``\ .

Don't use backticks when a :ref:`ref <ref>` link
to the corresponding object could be used.

When appropriate, longer code snippets and examples should be moved
to the :file:`{project}/examples/` directory in the relevant subproject
so that they can be appropriately unit tested.
They then can be included by using the :rst:dir:`literalinclude` directive.
If only a part of the file is needed in a given area,
use the ``:pyobject:`` option to extract it by :term:`FQON`,
not via line numbers, which can change and break documentation easily.

Otherwise, they can use the :rst:dir:`code-block` directive::

    .. code-block:: python

        class Echo(protocol.Protocol):
            def dataReceived(self, data):
                self.transport.write(data)

which will render as:

    .. code-block:: python

        class Echo(protocol.Protocol):
            def dataReceived(self, data):
                self.transport.write(data)

or by simply ending a line with `:: <http://sphinx-doc.org/markup/code.html#showing-code-examples>`_\ ,
which will use the default language highlighting for the document
(Python if unspecified or controllable via the :rst:dir:`highlight` directive).
No special language or option is necessary to recognize console sessions,
just include them in a code or literal block and they will be recognized.


Footnotes
^^^^^^^^^

`Sphinx footnotes <http://sphinx-doc.org/rest.html#footnotes>`_ can be created
in either the named or numbered variety.


Links
^^^^^


Documentation Source Layout
---------------------------

Documentation should be formatted with a single sentence or clause per line.
This results in diffs that are easier to read,
making documentation maintenance easier.

.. note::

     Most of the existing documentation doesn't follow this policy.
     When making changes, new sections should follow the above policy,
     and existing changed paragraphs be reformatted.

Documentation should be wrapped to 79 characters in rst source files.
Links or other long markup may extend beyond when necessary.


__all__
-------

``__all__`` is a module level list of strings,
naming objects in the module that are public.
Make sure publically exported classes, functions and constants are listed here.
