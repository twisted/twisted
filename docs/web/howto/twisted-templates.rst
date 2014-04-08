
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

HTML Templating with twisted.web.template
=========================================






A Very Quick Introduction To Templating In Python
-------------------------------------------------



HTML templating is the process of transforming a template document (one which
describes style and structure, but does not itself include any content) into
some HTML output which includes information about objects in your application.
There are many, many libraries for doing this in Python: to name a few, `jinja2 <http://jinja.pocoo.org/>`_ , `django templates <http://docs.djangoproject.com/en/dev/ref/templates/>`_ ,
and `clearsilver <http://www.clearsilver.net/>`_ .  You can easily use
any of these libraries in your Twisted Web application, either by running them
as :doc:`WSGI applications <web-in-60/wsgi>` or by calling your
preferred templating system's APIs to produce their output as strings, and then
writing those strings to :api:`twisted.web.http.Request.write <Request.write>` .



Before we begin explaining how to use it, I'd like to stress that you
don't *need* to use Twisted's templating system if you prefer some other
way to generate HTML.  Use it if it suits your personal style or your
application, but feel free to use other things.  Twisted includes templating for
its own use, because the ``twisted.web`` server needs to produce HTML
in various places, and we didn't want to add another large dependency for that.
Twisted is *not* in any way incompatible with other systems, so that has
nothing to do with the fact that we use our own.








twisted.web.template - Why And How you Might Want to Use It
-----------------------------------------------------------



Twisted includes a templating system, :api:`twisted.web.template <twisted.web.template>` .  This can be convenient for Twisted
applications that want to produce some basic HTML for a web interface without an
additional dependency.



``twisted.web.template`` also includes
support for :api:`twisted.internet.defer.Deferred <Deferred>` s, so
you can incrementally render the output of a page based on the results of :api:`twisted.internet.defer.Deferred <Deferred>` s that your application
has returned.  This feature is fairly unique among templating libraries.




In :api:`twisted.web.template <twisted.web.template>` , templates are XHTML files
which also contain a special namespace for indicating dynamic portions of the
document. For example:




:download:`template-1.xml <listings/template-1.xml>`

.. literalinclude:: listings/template-1.xml

The basic unit of templating is :api:`twisted.web.template.Element <twisted.web.template.Element>` . An Element is given a way of
loading a bit of markup like the above example, and knows how to
correlate ``render``  attributes within that markup to Python methods
exposed with :api:`twisted.web.template.renderer <twisted.web.template.renderer>` :


:download:`element_1.py <listings/element_1.py>`

.. literalinclude:: listings/element_1.py

In order to combine the two, we must render the element.  For this simple
example, we can use the :api:`twisted.web.template.flattenString <flattenString>`  API, which will convert a
single template object - such as an :api:`twisted.web.template.Element <Element>`  - into a :api:`twisted.internet.defer.Deferred <Deferred>`  which fires with a single string,
the HTML output of the rendering process.


:download:`render_1.py <listings/render_1.py>`

.. literalinclude:: listings/render_1.py


This short program cheats a little bit; we know that there are no :api:`twisted.internet.defer.Deferred <Deferred>` s in the template which
require the reactor to eventually fire; therefore, we can simply add a callback
which outputs the result.  Also, none of the ``renderer`` functions
require the ``request`` object, so it's acceptable to
pass ``None`` through here.  (The 'request' object here is used only to
relay information about the rendering process to each renderer, so you may
always use whatever object makes sense for your application.  Note, however,
that renderers from library code may require an :api:`twisted.web.iweb.IRequest <IRequest>` .)




If you run it yourself, you can see that it produces the following output:




:download:`output-1.html <listings/output-1.html>`

.. literalinclude:: listings/output-1.html

The third parameter to a renderer method is a :api:`twisted.web.template.Tag <Tag>`  object which represents the XML element
with the ``t:render``  attribute in the template. Calling a :api:`twisted.web.template.Tag <Tag>`  adds children to the element
in the DOM, which may be strings, more :api:`twisted.web.template.Tag <Tag>` s, or other renderables such as :api:`twisted.web.template.Element <Element>` s.
For example, to make the header and footer bold:


:download:`element_2.py <listings/element_2.py>`

.. literalinclude:: listings/element_2.py

Rendering this in a similar way to the first example would produce:



:download:`output-2.html <listings/output-2.html>`

.. literalinclude:: listings/output-2.html

In addition to adding children, call syntax can be used to set attributes on a
tag. For example, to change the ``id``  on the ``div``  while
adding children:



:download:`element_3.py <listings/element_3.py>`

.. literalinclude:: listings/element_3.py

And this would produce the following page:



:download:`output-3.html <listings/output-3.html>`

.. literalinclude:: listings/output-3.html



Calling a tag mutates it, it and returns the tag itself, so you can pass it
forward and call it multiple times if you have multiple children or attributes
to add to it. :api:`twisted.web.template <twisted.web.template>` also exposes some
convenient objects for building more complex markup structures from within
renderer methods in the ``tags`` object.  In the examples above, we've
only used ``tags.p`` and ``tags.b`` , but there should be a ``tags.x`` for each *x* which is a valid HTML tag.  There may be
some omissions, but if you find one, please feel free to file a bug.





Template Attributes
~~~~~~~~~~~~~~~~~~~


``t:attr``  tags allow you to set HTML attributes
(like ``href``  in an ``<a href="...`` ) on an enclosing
element.



Slots
~~~~~


``t:slot``  tags allow you to specify "slots" which you can
conveniently fill with multiple pieces of data straight from your Python
program.

The following example demonstrates both ``t:attr`` 
and ``t:slot``  in action. Here we have a layout which displays a person's
profile on your snazzy new Twisted-powered social networking site. We use
the ``t:attr``  tag to drop in the "src" attribute on the profile picture,
where the actual value of src attribute gets specified by a ``t:slot`` 
tag *within*  the ``t:attr``  tag. Confused? It should make more
sense when you see the code:



:download:`slots-attributes-1.xml <listings/slots-attributes-1.xml>`

.. literalinclude:: listings/slots-attributes-1.xml



:download:`slots_attributes_1.py <listings/slots_attributes_1.py>`

.. literalinclude:: listings/slots_attributes_1.py



:download:`slots-attributes-output.html <listings/slots-attributes-output.html>`

.. literalinclude:: listings/slots-attributes-output.html



Iteration
~~~~~~~~~



Often, you will have a sequence of things, and want to render each of them,
repeating a part of the template for each one. This can be done by
cloning ``tag`` in your renderer:





:download:`iteration-1.xml <listings/iteration-1.xml>`

.. literalinclude:: listings/iteration-1.xml



:download:`iteration-1.py <listings/iteration-1.py>`

.. literalinclude:: listings/iteration-1.py



:download:`iteration-output-1.xml <listings/iteration-output-1.xml>`

.. literalinclude:: listings/iteration-output-1.xml


This renderer works because a renderer can return anything that can be
rendered, not just ``tag`` . In this case, we define a generator, which
returns a thing that is iterable. We also could have returned
a ``list`` . Anything that is iterable will be rendered by :api:`twisted.web.template <twisted.web.template>` rendering each item in it. In
this case, each item is a copy of the tag the renderer received, each filled
with the name of a widget.





Sub-views
~~~~~~~~~



Another common pattern is to delegate the rendering logic for a small part of
the page to a separate ``Element`` .  For example, the widgets from the
iteration example above might be more complicated to render.  You can define
an ``Element`` subclass which can render a single widget.  The renderer
method on the container can then yield instances of this
new ``Element`` subclass.





:download:`subviews-1.xml <listings/subviews-1.xml>`

.. literalinclude:: listings/subviews-1.xml



:download:`subviews-1.py <listings/subviews-1.py>`

.. literalinclude:: listings/subviews-1.py



:download:`subviews-output-1.xml <listings/subviews-output-1.xml>`

.. literalinclude:: listings/subviews-output-1.xml


``TagLoader`` lets the portion of the overall template related to
widgets be re-used for ``WidgetElement`` , which is otherwise a
normal ``Element`` subclass not much different
from ``WidgetsElement`` .  Notice that the *name* renderer on
the ``span`` tag in this template is satisfied
from ``WidgetElement`` , not ``WidgetsElement`` .





Transparent
~~~~~~~~~~~


Note how renderers, slots and attributes require you to specify a renderer on
some outer HTML element. What if you don't want to be forced to add an element
to your DOM just to drop some content into it? Maybe it messes with your
layout, and you can't get it to work in IE with that extra ``div`` 
tag? Perhaps you need ``t:transparent`` , which allows you to drop some
content in without any surrounding "container" tag. For example:



:download:`transparent-1.xml <listings/transparent-1.xml>`

.. literalinclude:: listings/transparent-1.xml



:download:`transparent_element.py <listings/transparent_element.py>`

.. literalinclude:: listings/transparent_element.py



:download:`transparent-output.html <listings/transparent-output.html>`

.. literalinclude:: listings/transparent-output.html



Quoting
-------


:api:`twisted.web.template <twisted.web.template>`  will quote any strings that place
into the DOM.  This provides protection against `XSS attacks <http://en.wikipedia.org/wiki/Cross-site_scripting>`_ , in
addition to just generally making it easy to put arbitrary strings onto a web
page, without worrying about what they might have in them.  This can easily be
demonstrated with an element using the same template from our earlier examples.
Here's an element that returns some "special" characters in HTML ('<', '>',
and '"', which is special in attribute values):



:download:`quoting_element.py <listings/quoting_element.py>`

.. literalinclude:: listings/quoting_element.py

Note that they are all safely quoted in the output, and will appear in a web
browser just as you returned them from your Python method:



:download:`quoting-output.html <listings/quoting-output.html>`

.. literalinclude:: listings/quoting-output.html



Deferreds
---------


Finally, a simple demonstration of Deferred support, the unique feature of :api:`twisted.web.template <twisted.web.template>` .  Simply put, any renderer may
return a Deferred which fires with some template content instead of the template
content itself.  As shown above, :api:`twisted.web.template.flattenString <flattenString>`  will return a Deferred that
fires with the full content of the string.  But if there's a lot of content, you
might not want to wait before starting to send some of it to your HTTP client:
for that case, you can use :api:`twisted.web.template.flatten <flatten>` .
It's difficult to demonstrate this directly in a browser-based application;
unless you insert very long delays before firing your Deferreds, it just looks
like your browser is instantly displaying everything.  Here's an example that
just prints out some HTML template, with markers inserted for where certain
events happen:



:download:`wait_for_it.py <listings/wait_for_it.py>`

.. literalinclude:: listings/wait_for_it.py

If you run this example, you should get the following output:



:download:`waited-for-it.html <listings/waited-for-it.html>`

.. literalinclude:: listings/waited-for-it.html

This demonstrates that part of the output (everything up to
"``[[[In progress...`` ") is written out immediately as it's rendered.
But once it hits the Deferred, ``WaitForIt`` 's rendering needs to pause
until ``.callback(...)``  is called on that Deferred.  You can see that
no further output is produced until the message indicating that the Deferred is
being fired is complete.  By returning Deferreds and using :api:`twisted.web.template.flatten <flatten>` , you can avoid buffering large
amounts of data.



A Brief Note on Formats and DOCTYPEs
------------------------------------




The goal of ``twisted.web.template`` is to emit both valid `HTML <http://whatwg.org/html>`_ or `XHTML <http://www.whatwg.org/specs/web-apps/current-work/multipage/the-xhtml-syntax.html#the-xhtml-syntax>`_ .
However, in order to get the maximally standards-compliant output format you
desire, you have to know which one you want, and take a few simple steps to emit
it correctly.  Many browsers will probably work with most output if you ignore
this section entirely, but `the    HTML specification recommends that you specify an appropriate DOCTYPE <http://www.whatwg.org/specs/web-apps/current-work/multipage/syntax.html#the-doctype>`_ .





As a ``DOCTYPE`` declaration in your template would describe the
template itself, rather than its output, it won't be included in your output.
If you wish to annotate your template output with a DOCTYPE, you will have to
write it to the browser out of band.  One way to do this would be to simply
do ``request.write('<!DOCTYPE html>\n')`` when you are ready to
begin emitting your response.  The same goes for an XML ``DOCTYPE`` 
declaration.




``twisted.web.template`` will remove the ``xmlns`` attributes
used to declare
the ``http://twistedmatrix.com/ns/twisted.web.template/0.1`` namespace,
but it will not modify other namespace declaration attributes.  Therefore if you
wish to serialize in HTML format, you should not use other namespaces; if you
wish to serialize to XML, feel free to insert any namespace declarations that
are appropriate, and they will appear in your output.



.. note::
   
   This relaxed approach is correct in many cases.  However, in certain contexts -
   especially <script> and <style> tags - quoting rules differ in
   significant ways between HTML and XML, and between different browsers' parsers
   in HTML.  If you want to generate dynamic content inside a script or stylesheet,
   the best option is to load the resource externally so you don't have to worry
   about quoting rules.  The second best option is to strictly configure your
   content-types and DOCTYPE declarations for XML, whose quoting rules are simple
   and compatible with the approach that ``twisted.web.template``  takes.
   And, please remember: regardless of how you put it there, any user input placed
   inside a <script> or <style> tag is a potential security issue.





A Bit of History
----------------



Those of you who used Divmod Nevow may notice some
similarities.  ``twisted.web.template`` is in fact derived from the
latest version of Nevow, but includes only the latest components from Nevow's
rendering pipeline, and does not have any of the legacy compatibility layers
that Nevow grew over time.  This should make
using ``twisted.web.template`` a similar experience for many long-time
users of Twisted who have previously used Nevow for its twisted-friendly
templating, but more straightforward for new users.


