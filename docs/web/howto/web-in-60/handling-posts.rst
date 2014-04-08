
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Handling POSTs
==============





All of the previous examples have focused on ``GET`` 
requests. Unlike ``GET`` requests, ``POST`` requests can have
a request body - extra data after the request headers; for example, data
representing the contents of an HTML form. Twisted Web makes this data available
to applications via the :api:`twisted.web.server.Request <Request>` object.




Here's an example web server which renders a static HTML form and then
generates a dynamic page when that form is posted back to it. Disclaimer: While
it's convenient for this example, it's often not a good idea to make a resource
that ``POST`` s to itself; this isn't about Twisted Web, but the nature
of HTTP in general; if you do this in a real application, make sure you
understand the possible negative consequences.




As usual, we start with some imports. In addition to the Twisted imports,
this example uses the ``cgi`` module to `escape user-enteredcontent <http://en.wikipedia.org/wiki/Cross-site_scripting>`_ for inclusion in the output.





.. code-block:: python

    
    from twisted.web.server import Site
    from twisted.web.resource import Resource
    from twisted.internet import reactor
    
    import cgi




Next, we'll define a resource which is going to do two things. First, it will
respond to ``GET`` requests with a static HTML form:





.. code-block:: python

    
    class FormPage(Resource):
        def render_GET(self, request):
            return '<html><body><form method="POST"><input name="the-field" type="text" /></form></body></html>'




This is similar to the resource used in a :doc:`previous installment <dynamic-content>` . However, we'll now add
one more method to give it a second behavior; this ``render_POST`` 
method will allow it to accept ``POST`` requests:





.. code-block:: python

    
    ...
        def render_POST(self, request):
            return '<html><body>You submitted: %s</body></html>' % (cgi.escape(request.args["the-field"][0]),)




The main thing to note here is the use
of ``request.args`` . This is a dictionary-like object that
provides access to the contents of the form. The keys in this
dictionary are the names of inputs in the form. Each value is a list
containing strings (since there can be multiple inputs with the same
name), which is why we had to extract the first element to pass
to ``cgi.escape`` . ``request.args`` will be
populated from form contents whenever a ``POST`` request is
made with a content type
of ``application/x-www-form-urlencoded`` 
or ``multipart/form-data`` (it's also populated by query
arguments for any type of request).




Finally, the example just needs the usual site creation and port setup:





.. code-block:: python

    
    root = Resource()
    root.putChild("form", FormPage())
    factory = Site(root)
    reactor.listenTCP(8880, factory)
    reactor.run()




Run the server and
visit `http://localhost:8880/form <http://localhost:8880/form>`_ ,
submit the form, and watch it generate a page including the value you entered
into the single field.




Here's the complete source for the example:





.. code-block:: python

    
    from twisted.web.server import Site
    from twisted.web.resource import Resource
    from twisted.internet import reactor
    
    import cgi
    
    class FormPage(Resource):
        def render_GET(self, request):
            return '<html><body><form method="POST"><input name="the-field" type="text" /></form></body></html>'
    
        def render_POST(self, request):
            return '<html><body>You submitted: %s</body></html>' % (cgi.escape(request.args["the-field"][0]),)
    
    root = Resource()
    root.putChild("form", FormPage())
    factory = Site(root)
    reactor.listenTCP(8880, factory)
    reactor.run()



