
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
:py:attr:`content <twisted.web.iweb.IRequest.content>` attribute.




The only significant difference between this example and the previous is that
instead of accessing ``request.args``
in ``render_POST`` , it
uses ``request.content`` to get the request's body
directly:





.. code-block:: python


    ...
        def render_POST(self, request):
            content = request.content.read().decode("utf-8")
            escapedContent = cgi.escape(content)
            return (b"<!DOCTYPE html><html><head><meta charset='utf-8'>"
                    b"<title></title></head><body>"
                    b"You submitted: " +
                    escapedContent.encode("utf-8"))




``request.content`` is a file-like object, so the
body is read from it.  The exact type may vary, so avoid relying on non-file
methods you may find (such as ``getvalue`` when ``request.content`` happens
to be a ``BytesIO`` instance).




Here's the complete source for this example - again, almost identical to the
previous ``POST`` example, with
only ``render_POST`` changed:





.. code-block:: python


    from twisted.web.server import Site
    from twisted.web.resource import Resource
    from twisted.internet import reactor, endpoints

    import cgi

    class FormPage(Resource):
        def render_GET(self, request):
            return (b"<!DOCTYPE html><html><head><meta charset='utf-8'>"
                    b"<title></title></head><body>"
                    b"<form method='POST'><input name='the-field'></form>")

        def render_POST(self, request):
            content = request.content.read().decode("utf-8")
            escapedContent = cgi.escape(content)
            return (b"<!DOCTYPE html><html><head><meta charset='utf-8'>"
                    b"<title></title></head><body>"
                    b"You submitted: " +
                    escapedContent.encode("utf-8"))

    root = Resource()
    root.putChild(b"form", FormPage())
    factory = Site(root)
    endpoint = endpoints.TCP4ServerEndpoint(reactor, 8880)
    endpoint.listen(factory)
    reactor.run()



