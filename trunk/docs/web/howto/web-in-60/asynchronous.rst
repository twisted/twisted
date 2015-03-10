
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Asynchronous Responses
======================





In all of the previous examples, the resource examples presented generated
responses immediately. One of the features of prime interest of Twisted Web,
though, is the ability to generate a response over a longer period of time while
leaving the server free to respond to other requests. In other words,
asynchronously. In this installment, we'll write a resource like this.




A resource that generates a response asynchronously looks like one that
generates a response synchronously in many ways. The same base
class, :api:`twisted.web.resource.Resource <Resource>` , is used
either way; the same render methods are used. There are three basic differences,
though.




First, instead of returning the string which will be used as the
body of the response, the resource uses :api:`twisted.web.http.Request.write <Request.write>` . This method can be
called repeatedly. Each call appends another string to the response
body. Second, when the entire response body has been passed
to ``Request.write`` , the application must
call :api:`twisted.web.http.Request.finish <Request.finish>` . As you might expect
from the name, this ends the response. Finally, in order to make
Twisted Web not end the response as soon as the render method returns,
the render method must return ``NOT_DONE_YET`` . Consider this
example:





.. code-block:: python

    
    from twisted.web.resource import Resource
    from twisted.web.server import NOT_DONE_YET
    from twisted.internet import reactor
    
    class DelayedResource(Resource):
        def _delayedRender(self, request):
            request.write("<html><body>Sorry to keep you waiting.</body></html>")
            request.finish()
    
        def render_GET(self, request):
            reactor.callLater(5, self._delayedRender, request)
            return NOT_DONE_YET




If you're not familiar with the reactor :api:`twisted.internet.interfaces.IReactorTime.callLater <callLater>` 
method, all you really need to know about it to understand this
example is that the above usage of it arranges to
have ``self._delayedRender(request)`` run about 5 seconds
after ``callLater`` is invoked from this render method and
that it returns immediately.




All three of the elements mentioned earlier can be seen in this
example. The resource uses ``Request.write`` to set the
response body. It uses ``Request.finish`` after the entire
body has been specified (all with just one call to write in this
case). Lastly, it returns ``NOT_DONE_YET`` from its render
method. So there you have it, asynchronous rendering with Twisted
Web.




Here's a complete rpy script based on this resource class (see the :doc:`previous example <rpy-scripts>` if you need a reminder about rpy
scripts):





.. code-block:: python

    
    from twisted.web.resource import Resource
    from twisted.web.server import NOT_DONE_YET
    from twisted.internet import reactor
    
    class DelayedResource(Resource):
        def _delayedRender(self, request):
            request.write("<html><body>Sorry to keep you waiting.</body></html>")
            request.finish()
    
        def render_GET(self, request):
            reactor.callLater(5, self._delayedRender, request)
            return NOT_DONE_YET
    
    resource = DelayedResource()




Drop this source into a ``.rpy`` file and fire up a server
using ``twistd -n web --path /directory/containing/script/.`` 
You'll see that loading the page takes 5 seconds. If you try to load a
second before the first completes, it will also take 5 seconds from
the time you request it (but it won't be delayed by any other
outstanding requests).




Something else to consider when generating responses asynchronously is that
the client may not wait around to get the response to its
request. A :doc:`subsequent example <interrupted>` demonstrates how
to detect that the client has abandoned the request and that the server
shouldn't bother to finish generating its response.



