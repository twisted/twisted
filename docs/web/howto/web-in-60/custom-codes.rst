
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Custom Response Codes
=====================





The previous example introduced :api:`twisted.web.error.NoResource <NoResource>` , a Twisted Web error resource which
responds with a 404 (not found) code. This example will cover the APIs
that ``NoResource`` uses to do this so that you can generate your own
custom response codes as desired.




First, the now-standard import preamble:





.. code-block:: python

    
    from twisted.web.server import Site
    from twisted.web.resource import Resource
    from twisted.internet import reactor




Now we'll define a new resource class that always returns a 402 (payment
required) response. This is really not very different from the resources that
was defined in previous examples. The fact that it has a response code other
than 200 doesn't change anything else about its role. This will require using
the request object, though, which none of the previous examples have done.




The :api:`twisted.web.server.Request <Request>` object has
shown up in a couple of places, but so far we've ignored it. It is a parameter
to the :api:`twisted.web.resource.Resource.getChild <getChild>` 
API as well as to render methods such as ``render_GET`` . As you might
have suspected, it represents the request for which a response is to be
generated. Additionally, it also represents the response being generated. In
this example we're going to use its :api:`twisted.web.http.Request.setResponseCode <setResponseCode>` method to - you guessed
it - set the response's status code.





.. code-block:: python

    
    class PaymentRequired(Resource):
        def render_GET(self, request):
            request.setResponseCode(402)
            return "<html><body>Please swipe your credit card.</body></html>"




Just like the other resources I've demonstrated, this one returns a
string from its ``render_GET`` method to define the body of
the response. All that's different is the call
to ``setResponseCode`` to override the default response code,
200, with a different one.




Finally, the code to set up the site and reactor. We'll put an instance of
the above defined resource at ``/buy`` :





.. code-block:: python

    
    root = Resource()
    root.putChild("buy", PaymentRequired())
    factory = Site(root)
    reactor.listenTCP(8880, factory)
    reactor.run()




Here's the complete example:





.. code-block:: python

    
    from twisted.web.server import Site
    from twisted.web.resource import Resource
    from twisted.internet import reactor
    
    class PaymentRequired(Resource):
        def render_GET(self, request):
            request.setResponseCode(402)
            return "<html><body>Please swipe your credit card.</body></html>"
    
    root = Resource()
    root.putChild("buy", PaymentRequired())
    factory = Site(root)
    reactor.listenTCP(8880, factory)
    reactor.run()




Run the server and visit ``http://localhost:8880/buy`` in your
browser. It'll look pretty boring, but if you use Firefox's View Page Info
right-click menu item (or your browser's equivalent), you'll be able to see that
the server indeed sent back a 402 response code.



