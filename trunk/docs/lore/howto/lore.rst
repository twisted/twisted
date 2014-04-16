
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Using the Lore Documentation System
===================================






Writing Lore Documents
----------------------




Overview
~~~~~~~~



Lore documents are a special subset of XHTML documents. They use specific
subset of XHTML, together with custom classes, to allow a wide variety of
document elements, including some Python-specific ones. Lore documents, in
particular, are well-formed XML documents. XML can be written using a wide
variety of tools: from run of the mill editors such as vi, through editors
with XML help like EMACS and ending with XML specific tools like (need name
of XML editor here). Here, we will not cover the specifics of writing XML
documents, except for a very broad overview.




XML documents contain elements, which are delimited by an opening
tag which looks like ``<tag-name attribute="value">`` 
and ends with a closing tag, which looks
like ``</tag-name>`` . If an elements happen to contain
nothing, it can be shortened to ``<tag-name />`` . Elements can contain other elements, or text. Text can
contain any characters except <, > and &. These characters
are rendered by &lt;, &gt; and &amp;, respectively.




A Lore document is a single ``html`` element. Inside this
element, there are exactly two top-level elements: ``head`` 
and ``body`` . The ``head`` element must contain
exactly one element: ``title`` , containing the title of the
document.  Most of the document will be contained in
the ``body`` element.  The ``body`` element must
start with an ``h1`` (top-level header) element, which
contains the exact same content as the ``title`` element.




Thus, a fairly minimal Lore document might look like:





::

    
    <html>
    <head><title>Title</title></head>
    <body><h1>Title</h1></body>
    </html>





Elements and Their Uses
~~~~~~~~~~~~~~~~~~~~~~~



+---------------------+----------------------------------------------------------------------------------------------------------------------+
| Element             | Description                                                                                                          |
+=====================+======================================================================================================================+
| ``p``               | The paragraph element. Most of the document should be inside paragraphs.                                             |
+---------------------+----------------------------------------------------------------------------------------------------------------------+
| ``span``            | The span element is an element which has no meaning -- unless it has a                                               |
|                     | special ``class``  attributes. The following classes have the stated                                                 |
|                     | meanings:                                                                                                            |
|                     |                                                                                                                      |
|                     |                                                                                                                      |
|                     |                                                                                                                      |
|                     |                                                                                                                      |
|                     | ``footnote``                                                                                                         |
|                     |                                                                                                                      |
|                     |   a small comment which should not be inside the main text-flow.                                                     |
|                     |                                                                                                                      |
|                     | ``manhole-output``                                                                                                   |
|                     |                                                                                                                      |
|                     |   This signifies, within a manhole transcript, that the enclosed text is                                             |
|                     |   the output and not something the user has to input.                                                                |
|                     |                                                                                                                      |
|                     | ``index``                                                                                                            |
|                     |                                                                                                                      |
|                     |   This should be an *empty* element, with an attribute                                                               |
|                     |   ``value`` . That attribute should be an index term, in the                                                         |
|                     |   format of ``generic!specific!more specific`` . Usually,                                                            |
|                     |   you will only have one level, in which case ``value="term"``                                                       |
|                     |   works.                                                                                                             |
+---------------------+----------------------------------------------------------------------------------------------------------------------+
| ``div``             | The div element is equivalent to a span, except it always appears outside                                            |
|                     | paragraphs. The following classes have the given meanings:                                                           |
|                     |                                                                                                                      |
|                     |                                                                                                                      |
|                     |                                                                                                                      |
|                     | ``note``                                                                                                             |
|                     |                                                                                                                      |
|                     |   A short note which is not necessary for the understanding of the text.                                             |
|                     |                                                                                                                      |
|                     | ``doit``                                                                                                             |
|                     |                                                                                                                      |
|                     |   An indication that the discussed feature is not complete or implemented                                            |
|                     |   yet.                                                                                                               |
|                     |                                                                                                                      |
|                     | ``boxed``                                                                                                            |
|                     |                                                                                                                      |
|                     |   An indication that the text should be clearly separated from its                                                   |
|                     |   surroundings.                                                                                                      |
+---------------------+----------------------------------------------------------------------------------------------------------------------+
| ``a``               | This element can have several meanings, depending on the attributes:                                                 |
|                     |                                                                                                                      |
|                     |                                                                                                                      |
|                     |                                                                                                                      |
|                     | ``name``  attribute                                                                                                  |
|                     |                                                                                                                      |
|                     |   Add a label to the current position, which might be used in this document                                          |
|                     |   or other documents to refer to.                                                                                    |
|                     |                                                                                                                      |
|                     | ``href=URL``                                                                                                         |
|                     |                                                                                                                      |
|                     |   Refer to some WWW resource.                                                                                        |
|                     |                                                                                                                      |
|                     | ``href=relative-path`` , ``href=relative-path#label``  or                                                            |
|                     |     ``href=#label``                                                                                                  |
|                     |                                                                                                                      |
|                     |   Refer to a position in a Lore resource.  By default, relative links to                                             |
|                     |   ``.xhtml`` files are changed to point to a ``.html`` file.                                                         |
|                     |   If you need a link to a local non-Lore .xhtml file, use                                                            |
|                     |   ``class=absolute`` to make Lore treat it as an absolute link.                                                      |
|                     |                                                                                                                      |
|                     | ``href=relative-path``  with ``class=py-listing``  or                                                                |
|                     |     ``class=html-listing``                                                                                           |
|                     |                                                                                                                      |
|                     |   Indicate the given resource is a part of the text flow, and should be                                              |
|                     |   inlined (and if possible, syntax highlighted).                                                                     |
+---------------------+----------------------------------------------------------------------------------------------------------------------+
| ``ol`` , ``ul``     | A list. It can be enumerated or bulleted. Inside a list, the                                                         |
|                     | element ``li``  (for a list element) is valid.                                                                       |
+---------------------+----------------------------------------------------------------------------------------------------------------------+
| ``h2`` , ``h3``     | Second- and third-level section headings.                                                                            |
+---------------------+----------------------------------------------------------------------------------------------------------------------+
| ``code``            | A string which has meaning to the computer. There are many possible                                                  |
|                     | classes:                                                                                                             |
|                     |                                                                                                                      |
|                     |                                                                                                                      |
|                     |                                                                                                                      |
|                     | ``API``                                                                                                              |
|                     |                                                                                                                      |
|                     |   A class, function or a module. It does not have to be a fully qualified                                            |
|                     |   name -- but if it isn't, a ``base`` attribute is necessary.                                                        |
|                     |                                                                                                                      |
|                     |   Example:                                                                                                           |
|                     |   ``<code class="API" base="urllib">urlencode<code>`` .                                                              |
|                     |                                                                                                                      |
|                     | ``shell``                                                                                                            |
|                     |                                                                                                                      |
|                     |   Shell (usually Bourne) code.                                                                                       |
|                     |                                                                                                                      |
|                     | ``python``                                                                                                           |
|                     |                                                                                                                      |
|                     |   Python code.                                                                                                       |
|                     |                                                                                                                      |
|                     | ``py-prototype``                                                                                                     |
|                     |                                                                                                                      |
|                     |   Function prototype.                                                                                                |
|                     |                                                                                                                      |
|                     | ``py-filename``                                                                                                      |
|                     |                                                                                                                      |
|                     |   Python file.                                                                                                       |
|                     |                                                                                                                      |
|                     | ``py-src-string``                                                                                                    |
|                     |                                                                                                                      |
|                     |   Python string.                                                                                                     |
|                     |                                                                                                                      |
|                     | ``py-signature``                                                                                                     |
|                     |                                                                                                                      |
|                     |   Function signature.                                                                                                |
|                     |                                                                                                                      |
|                     | ``py-src-parameter``                                                                                                 |
|                     |                                                                                                                      |
|                     |   Parameter.                                                                                                         |
|                     |                                                                                                                      |
|                     | ``py-src-identifier``                                                                                                |
|                     |                                                                                                                      |
|                     |   Identifier.                                                                                                        |
|                     |                                                                                                                      |
|                     | ``py-src-keyword``                                                                                                   |
|                     |                                                                                                                      |
|                     |   Keyword.                                                                                                           |
+---------------------+----------------------------------------------------------------------------------------------------------------------+
| ``pre``             | Preformatted text, usually for file listings. It can be used with                                                    |
|                     | the ``python``  class to indicate Python syntax                                                                      |
|                     | coloring. Other possible classes are ``shell``  (to indicate a                                                       |
|                     | shell-transcript) or ``python-interpreter``  (to indicate an                                                         |
|                     | interactive interpreter transcript).                                                                                 |
+---------------------+----------------------------------------------------------------------------------------------------------------------+
| ``img``             | Insert the image indicated by the ``src``  attribute.                                                                |
+---------------------+----------------------------------------------------------------------------------------------------------------------+
| ``q``               | The quote signs (``"`` ) are not recommended                                                                         |
|                     | except in preformatted or code environment. Instead, quote by using the                                              |
|                     | ``q``  element which allows nested quotes and properly distinguishes                                                 |
|                     | opening quote from closing quote.                                                                                    |
+---------------------+----------------------------------------------------------------------------------------------------------------------+
| ``em`` , ``strong`` | Emphasise (or strongly emphasise) text.                                                                              |
+---------------------+----------------------------------------------------------------------------------------------------------------------+
| ``table``           | Tabular data. Inside a table, use the ``tr``                                                                         |
|                     | element for each rows, and inside it use either ``td``  for a regular                                                |
|                     | table cell or ``th``  for a table header (column or row).                                                            |
+---------------------+----------------------------------------------------------------------------------------------------------------------+
| ``blockquote``      | A long quote which should be properly seperated from the main text.                                                  |
+---------------------+----------------------------------------------------------------------------------------------------------------------+
| ``cite``            | Cite a resource.                                                                                                     |
+---------------------+----------------------------------------------------------------------------------------------------------------------+
| ``sub`` , ``sup``   | Subscripts and superscripts.                                                                                         |
+---------------------+----------------------------------------------------------------------------------------------------------------------+
| ``link``            | Currently, the only ``link``  elements supported                                                                     |
|                     | are for for indicating authorship. ``<link rel="author" href="author-address@examples.com" title="Author Name" />``  |
|                     | should be used to indicate authorship. Multiple instances                                                            |
|                     | are allowed, and indicate shared authorship.                                                                         |
+---------------------+----------------------------------------------------------------------------------------------------------------------+



Writing Lore XHTML Templates
----------------------------



One of Lore's output formats is XHTML. Lore itself is very markup-light,
but the output XHTML is much more markup intensive. Part of the auto-generated
markup is directed by a special template.




The output of Lore is inserted into template in the following way:





- The title is appended into each element with class ``title`` .
- The body is inserted into the first element that has class
  ``body`` .
- The table of contents is inserted into the first element that has class
  ``toc`` .





In particular, most of the header is not tampered with -- so it is
easy to indicate a CSS stylesheet in the template.





Using Lore to Generate HTML
---------------------------



After having written a template, the easiest way to build HTML from the Lore
document is by:





.. code-block:: console

    
    % lore --config template=mytemplate.tpl mydocument.xhtml




This will create a file called ``mydocument.html`` .




For example, to generate the HTML version of the Twisted docs from a SVN
checkout, do:





.. code-block:: console

    
    % lore --config template=doc/core/howto/template.tpl doc/core/howto/*.xhtml





In order to generate files with a different extension, use the ``--config`` commandline flag to tell the HTML output plugin to
use a different extension:




.. code-block:: console

    
    % lore --config ext=.html doc/core/howto/*.xhtml




Using Lore to Generate LaTex
----------------------------




Articles
~~~~~~~~




.. code-block:: console

    
    % lore --output latex mydocument.xhtml





Books
~~~~~



Have a Lore file for each section. Then, have a LaTeX file which inputs
all the given LaTeX files. Generate all the LaTeX files by using





.. code-block:: console

    
    % lore --output latex --config section *.xhtml




in the relevant directory.





Using Lore to Generate Slides
-----------------------------



Lore can also be used to generate slides for presentations.  The start
of a new slide is indicated by use of an h2 tag, with the content
between the opening and closing tags the title of the slide.  Slides
are generated by





.. code-block:: console

    
    % lore --input lore-slides myslides.xhtml




This, by default, will produce HTML output with one HTML file for
each slide.  For our example, the files would be named
myslides-<number>.html, where number is the slide number,
starting with 0 for the title slide.  Lore will look for a template
file, either indicated by the ``--config template=mytemplate.tpl`` or the default template.tpl in the
current directory.  An example slide template is found
in ``doc/examples/slides-template.tpl`` 




The slides module currently supports three major output types:
HTML, Magic Point, and LaTeX.  The options for the latter two will be
covered individually.





Magic Point Output
~~~~~~~~~~~~~~~~~~



Lore supports outputting to the Magic Point file format.
Magicpoint is a presentation program for X, which can be installed on
Debian by ``apt-get install mgp`` or by visiting `the Magic Point homepage <http://member.wide.ad.jp/wg/mgp/>`_ 
otherwise.  A template file is required, ``template.mgp`` is
shipped in the ``twisted/lore`` directory.  Magic Point
slides are generated by 





.. code-block:: console

    
    % lore --input lore-slides --output mgp \
      --config template=~/Twisted/twisted/lore/template.mgp \
      myslides.xhtml




That will produce ``myslides.mgp`` .





LaTeX Output
~~~~~~~~~~~~



Lore can also produce slides in LaTeX format.  It supports three
main styles: one slide per page, two per page, and Prosper format,
with the ``--config`` parameters
being ``page`` , ``twopage`` ,
and ``prosper`` respectively. Prosper is a LaTeX class for
creating slides, which can be installed on Debian by ``apt-get install prosper`` or by
visiting `theProsper SourceForge page <http://sourceforge.net/projects/prosper/>`_ .  LaTeX format slides (using the Prosper
option, for example) are generated by





.. code-block:: console

    
    % lore --input lore-slides --output latex \
      --config prosper myslides.xhtml




This will generate ``myslides.tex`` file that can be processed
with ``latex`` or ``pdftex`` or the appropriate
LaTeX processing command.





Linting
-------




::

    
    % lore --output lint mydocument.xhtml




This will generate compiler-style (file:line:column:message) warnings.
It is possible to integrate these warnings into a smart editor such as
EMACS, but it has not been done yet.



