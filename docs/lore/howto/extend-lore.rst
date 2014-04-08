
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Extending the Lore Documentation System
=======================================






Overview
--------



The :doc:`Lore Documentation System <lore>` , out of the box, is
specialized for documenting Twisted.  Its markup includes CSS classes for
Python, HTML, filenames, and other Twisted-focused categories.  But don't
think this means Lore can't be used for other documentation tasks!  Lore is
designed to allow extensions, giving any Python programmer the ability to
customize Lore for documenting almost anything.




There are several reasons why you would want to extend Lore.  You may want
to attach file formats Lore does not understand to your documentation.  You
may want to create callouts that have special meanings to the reader, to give a
memorable appearance to text such as, "WARNING: This software was written by a frothing madman!" You may want to create color-coding for a different
programming language, or you may find that Lore does not provide you with
enough structure to mark your document up completely.  All of these situations
can be solved by creating an extension.





Inputs and Outputs
------------------



Lore works by reading the HTML source of your document, and
producing whatever output the user specifies on the command line.  If
the HTML document is well-formed XML that meets a certain minimum
standard, Lore will be able to to produce some output.  All Lore
extensions will be written to redefine the *input* , and most
will redefine the output in some way.  The name of the default input
is "lore" .  When you write your extension, you will come up with
a new name for your input, telling Lore what rules to use to process
the file.




Lore can produce XHTML, LaTeX, and DocBook document formats, which can be
displayed directly if you have a user agent capable of viewing them, or
processed into a third form such as PostScript or PDF.  Another output is
called "lint" , after the static-checking utility for C, and is used for
the same reason: to statically check input files for problems.  The"lint" output is just a stream of error messages, not a formatted
document, but is important because it gives users the ability to validate
their input before trying to process it.  For the first example, the only
output we will be concerned with is LaTeX.





Creating New Inputs
~~~~~~~~~~~~~~~~~~~


Create a new input to tell Lore that your document is marked up differently
from a vanilla Lore document.  This gives you the power to define a new tag 
class, for example:




::

    
    <p>The Frabjulon <span class="productname">Limpet 2000</span>
    is the <span class="marketinglie">industry-leading</span> aquatic 
    mollusc counter, bar none.</p>




The above HTML is an instance of a new input to Lore, which we will call
MyHTML, to differentiate it from the "lore" input.  We want it to have
the following markup: 





- A ``productname`` class for the <span> tag, which
  produces underlined text
- A ``marketinglie`` class for <span> tag, which
  produces larger type, bold text




Note that I chose class names that are valid Python identifiers.  You will
see why shortly.  To get these two effects in Lore's HTML output, all we have
to do is create a cascading stylesheet (CSS), and use it in the Lore XHTML
Template.  However, we also want these effects to work in LaTeX, and we want
the output of lint to produce no warnings when it sees lines with these 2
classes.  To make LaTeX and lint work, we start by creating a plugin.





:download:`a_lore_plugin.py <listings/lore/a_lore_plugin.py>`

.. literalinclude:: listings/lore/a_lore_plugin.py


Create this file in a ``twisted/plugins/`` 
directory (*not* a package) which is located in a directory in the
Python module search path.  See the :doc:`Twisted plugin howto <../../core/howto/plugin>` for more details on plugins.

  


Users of your extension will pass the value of your plugin's ``name`` attribute to lore with the ``--input`` parameter on the command line to select it.  For
example, to select the plugin defined above, a user would pass ``--input myhtml`` .  The ``moduleName`` attribute tells Lore where to find the code
implementing the plugin.  In particular, this module should have a ``factory`` attribute which defines a ``generator_`` -prefixed method for each output format it
supports.  Next we'll look at this module.





:download:`factory.py-1 <listings/lore/factory.py-1>`

.. literalinclude:: listings/lore/factory.py-1


In Listing 2, we create a subclass of ProcessingFunctionFactory.
This class provides a hook for you, a class variable
named ``latexSpitters`` .  This variable tells Lore what new
class will be generating LaTeX from your input format.  We
redefine ``latexSpitters`` to ``MyLatexSpitter`` in
the subclass because this class knows what to do with the new input we
have already defined.  Last, you must define the module-level
variable ``factory`` .  It should be
an instance with the same interface
as ``ProcessingFunctionFactory`` 
(e.g. an instance of a subclass, in this
case, ``MyProcessingFunctionFactory`` ).




Now let's actually write some code to generate the LaTeX.  Doing this
requires at least a familiarity with the LaTeX language.  Search Google for"latex tutorial" and you will find any number of useful LaTeX
resources.





:download:`spitters.py-1 <listings/lore/spitters.py-1>`

.. literalinclude:: listings/lore/spitters.py-1


The method ``visitNode_span_productname`` is our handler
for <span> tags with the ``class="productname"`` 
identifier.  Lore knows to try methods ``visitNode_span_*`` 
and ``visitNode_div_*`` whenever it encounters a new class in
one of these tags.  This is why the class names have to be valid
Python identifiers.




Now let's see what Lore does with these new classes with the following
input file:





:download:`1st_example.html <listings/lore/1st_example.html>`

.. literalinclude:: listings/lore/1st_example.html


First, verify that your package is laid out correctly.  Your directory
structure should look like this:





::

    
    1st_example.html
    myhtml/
           __init__.py
           factory.py
           spitters.py
    twisted/plugins/
           a_lore_plugin.py




In the parent directory of myhtml (that is, ``myhtml/..`` ), run
lore and pdflatex on the input:





.. code-block:: console

    
    $ lore --input myhtml --output latex 1st_example.html 
    [########################################] (*Done*)
    
    $ pdflatex 1st_example.tex
    [ . . . latex output omitted for brevity . . . ]
    Output written on 1st_example.pdf (1 page, 22260 bytes).
    Transcript written on 1st_example.log.




And here's what the rendered PDF looks like:






.. image:: ../img/myhtml-output.png






What happens when we run lore on this file using the lint output?





.. code-block:: console

    
    $ lore --input myhtml --output lint 1st_example.html
    1st_example.html:7:47: unknown class productname
    1st_example.html:8:38: unknown class marketinglie
    [########################################] (*Done*)




Lint reports these classes as errors, even though our spitter knows how to
process them.  To fix this problem, we must add to ``factory.py`` .





:download:`factory.py-2 <listings/lore/factory.py-2>`

.. literalinclude:: listings/lore/factory.py-2


The method ``getLintChecker`` is called
by Lore to produce the lint output.  This modification adds our classes to the
list of classes lint ignores:





.. code-block:: console

    
    $ lore --input myhtml --output lint 1st_example.html
    [########################################] (*Done*)
    $ # Hooray!




Finally, there are two other sub-outputs of LaTeX, for a total of three
different ways that Lore can produce LaTeX: the default way, which produces as
output an entire, self-contained LaTeX document; with ``--config section`` on the command line, which produces a
LaTeX \section; and with ``--config chapter`` , which
produces a LaTeX \chapter.  To support these options as well, the solution is
to make the new spitter class a mixin, and use it with the ``SectionLatexSpitter`` and ``ChapterLatexSpitter`` , respectively.
Comments in the following listings tell you everything you need to know about
making these simple changes:






- 
  
  :download:`factory.py-3 <listings/lore/factory.py-3>`
  
  .. literalinclude:: listings/lore/factory.py-3
  
- 
  
  :download:`spitters.py-2 <listings/lore/spitters.py-2>`
  
  .. literalinclude:: listings/lore/spitters.py-2
  






..    <h3>Creating New Outputs</h3>
   <p><div class="doit">write some stuff</div></p>
   
   <h2>Other Uses for Lore Extensions</h2>
   <p><div class="doit">write some stuff</div></p>
   
   <h3>Color-Code Programming Languages</h3>
   <p><div class="doit">write some stuff</div></p>
   
   <h3>Add New Structural Elements</h3>
   <p><div class="doit">write some stuff</div></p>
   
   <h3>Support New File Formats</h3>
   <p><div class="doit">write some stuff</div></p>

