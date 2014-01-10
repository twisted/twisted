
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Other Request Bodies
====================





The previous example demonstrated how to accept the payload of
a ``POST`` carrying HTML form data.  What about ``POST`` 
requests with data in some other format?  Or even ``PUT`` requests?
Here is an example which demonstrates how to get *any* request body,
regardless of its format - using the request's
:api:`twisted.web.iweb.IRequest.content <content>` attribute.




The only significant difference between this example and the previous is that
instead of accessing ``request.args`` 
in ``render_POST`` , it
uses ``request.content`` to get the request's body
directly:





.. code-block:: python

    
    ...
        def render_POST(self, request):
            return '<html><body>You submitted: %s</body></html>' % (cgi.escape(request.content.read()),)




``request.content`` is a file-like object, so the
body is read from it.  The exact type may vary, so avoid relying on non-file
methods you may find (such as ``getvalue`` when happens
to be a ``StringIO`` instance).




Here's the complete source for this example - again, almost identical to the
previous ``POST`` example, with
only ``render_POST`` changed:





.. code-block:: python

    
    from twisted.web.server import Site
    from twisted.web.resource import Resource
    from twisted.internet import reactor
    
    import cgi
    
    class FormPage(Resource):
        def render_GET(self, request):
            return '<html><body><form method="POST"><input name="the-field" type="text" /></form></body></html>'
    
        def render_POST(self, request):
            return '<html><body>You submitted: %s</body></html>' % (cgi.escape(request.content.read()),)
    
    root = Resource()
    root.putChild("form", FormPage())
    factory = Site(root)
    reactor.listenTCP(8880, factory)
    reactor.run()



