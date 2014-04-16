
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

HTML Documentation Standard for Twisted
=======================================






XHTML Layout
------------

      

Documentation should be formatted with a single sentence or clause per line.
This results in diffs that are easier to read,
making documentation maintenance easier.


      

.. note::
   
           
   
   
   - 
     Most of the existing documentation doesn't follow this policy.
     When making changes, new sections should follow the above policy,
     and existing changed paragraphs be reformatted.
   
         
   




    

Allowable Tags
--------------


    
Please try to restrict your HTML usage to the following tags (all only for the original logical purpose, and not whatever visual effect you see): ``<html>`` , ``<title>`` , ``<head>`` , ``<body>`` , ``<h1>`` , ``<h2`` , ``<h3>`` , ``<ol>`` , ``<ul>`` , ``<dl>`` , ``<li>`` ,   ``<dt>`` , ``<dd>`` , ``<p>`` , ``<code>`` ,  ``<img>`` ,  ``<blockquote>`` ,  ``<a>`` ,  ``<cite>`` , ``<div>`` , ``<span>`` , ``<strong>`` , ``<em>`` , ``<pre>`` , ``<q>`` , ``<table>`` , ``<tr>`` , ``<td>`` and ``<th>`` .

    


Please avoid using the quote sign (``"`` ) for quoting, and use the relevant html tags (``<q></q>`` ) -- it is impossible to distinguish right and left quotes with the quote sign, and some more sophisticated output methods work better with that distinction.

    



Multi-line Code Snippets
------------------------


    
Multi-line code snippets should be delimited with a
<pre> tag, with a mandatory "class" attribute. The
conventionalized classes are "python" , "python-interpreter" ,
and "shell" . For example:

    



"python"
~~~~~~~~

    
Original markup:
    

    
    
    
    ::
    
        
        <p>
        For example, this is how one defines a Resource:
        </p>
        
        <pre class="python">
        from twisted.web import resource
        
        class MyResource(resource.Resource):
            def render_GET(self, request):
                return "Hello, world!"
        </pre>
    
    
    
    
        
    
Rendered result:
    

    
    
    
    For example, this is how one defines a Resource:
    
    
    
    .. code-block:: python
    
        
        from twisted.web import resource
        
        class MyResource(resource.Resource):
            def render_GET(self, request):
                return "Hello, world!"
        
    
    
    
    
        
    
Note that you should never have leading indentation inside a
<pre> block -- this makes it hard for readers to
copy/paste the code.

    



"python-interpreter"
~~~~~~~~~~~~~~~~~~~~

    
Original markup:
    

    
    
    
    ::
    
        
        <pre class="python-interpreter">
        &gt;&gt;&gt; from twisted.web import resource
        &gt;&gt;&gt; class MyResource(resource.Resource):
        ...     def render_GET(self, request):
        ...         return "Hello, world!"
        ...
        &gt;&gt;&gt; MyResource().render_GET(None)
        "Hello, world!"
        </pre>
    
    
    
    
        
    
Rendered result:
    

    
    
    
    .. code-block:: pycon
    
        
        >>> from twisted.web import resource
        >>> class MyResource(resource.Resource):
        ...     def render_GET(self, request):
        ...         return "Hello, world!"
        ...
        >>> MyResource().render_GET(None)
        "Hello, world!"
    
    
    
    
        
    

"shell"
~~~~~~~

    
Original markup:
    

    
    
    
    ::
    
        
        <pre class="shell">
        $ twistd web --path /var/www
        </pre>
    
    
    
    
        
    
Rendered result:
    

    
    
    
    .. code-block:: console
    
        
        $ twistd web --path /var/www
    
    
    
    
        
    

Code inside paragraph text
--------------------------


    
For single-line code-snippets and attribute, method, class,
and module names, use the <code> tag, with a class of
"API" or "python" . During processing, module or class-names
with class "API" will automatically be looked up in the API
reference and have a link placed around it referencing the
actual API documents for that module/classname. If you wish to
reference an API document, then make sure you at least have a
single module-name so that the processing code will be able to
figure out which module or class you're referring to.

    


You may also use the ``base`` attribute in conjuction
with a class of "API" to indicate the module that should be prepended
to the module or classname.  This is to help keep the documentation
clearer and less cluttered by allowing links to API docs that don't
need the module name.
    


Original markup:
    

    
    
    
    ::
    
        
            <p>
        To add a <code class="API">twisted.web.static.File</code>
        instance to a <code class="API"
        base="twisted.web.resource">Resource</code> instance, do 
        <code class="python">myResource.putChild("resourcePath",
        File("/tmp"))</code>.  
            </p>
        
    
    
    
    
        
    
Rendered result:
    

    
    
    
    
    To add a :api:`twisted.web.static.File <twisted.web.static.File>` 
    instance to a :api:`twisted.web.resource.Resource <Resource>` 
    instance, do
    ``myResource.putChild("resourcePath", File("/tmp"))`` .
    
    
    
    
    
        
    

Headers
-------


    
It goes without mentioning that you should use <hN> in
a sane way -- <h1> should only appear once in the
document, to specify the title. Sections of the document should
use <h2>, sub-headers <h3>, and so on.

    



XHTML
-----


    
XHTML is mandatory. That means tags that don't have a
closing tag need a "/" ; for example, ``<hr />`` 
. Also, tags which have "optional" closing tags in HTML
*need* to be closed in XHTML; for example,
``<li>foo</li>`` 

    



Tag Case
--------


    
All tags will be done in lower-case. XHTML demands this, and
so do I. :-)

    



Footnotes
---------


    
Footnotes are enclosed inside 
``<span class="footnote"></span>`` . They must not
contain any markup.

    



Suggestions
-----------


    
Use ``lore -o lint`` to check your documentation
is not broken. ``lore -o lint`` will never change
your HTML, but it will complain if it doesn't like it.

    


Don't use tables for formatting. 'nuff said.

    



__all__
-------

    
    
``__all__`` is a module level list of strings, naming
objects in the module that are public. Make sure publically exported classes,
functions and constants are listed here.

  

