
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Interrupted Responses
=====================





The previous example had a Resource that generates its response
asynchronously rather than immediately upon the call to its render method. When
generating responses asynchronously, the possibility is introduced that the
connection to the client may be lost before the response is generated. In such a
case, it is often desirable to abandon the response generation entirely, since
there is nothing to do with the data once it is produced. This example shows how
to be notified that the connection has been lost.




This example will build upon the :doc:`asynchronous responses example <asynchronous>` which simply (if not very realistically) generated its
response after a fixed delay. We will expand that resource so that as soon as
the client connection is lost, the delayed event is cancelled and the response
is never generated.




The feature this example relies on is provided by another :api:`twisted.web.server.Request <Request>` method: :api:`twisted.web.http.Request.notifyFinish <notifyFinish>` . This method returns a new
Deferred which will fire with ``None`` if the request is successfully
responded to or with an error otherwise - for example if the connection is lost
before the response is sent.




The example starts in a familiar way, with the requisite Twisted imports and
a resource class with the same ``_delayedRender`` used previously:





.. code-block:: python

    
    from twisted.web.resource import Resource
    from twisted.web.server import NOT_DONE_YET
    from twisted.internet import reactor
    
    class DelayedResource(Resource):
        def _delayedRender(self, request):
            request.write("<html><body>Sorry to keep you waiting.</body></html>")
            request.finish()




Before defining the render method, we're going to define an errback
(an errback being a callback that gets called when there's an error),
though. This will be the errback attached to the ``Deferred`` 
returned by ``Request.notifyFinish`` . It will cancel the
delayed call to ``_delayedRender`` .





.. code-block:: python

    
    ...
        def _responseFailed(self, err, call):
            call.cancel()




Finally, the render method will set up the delayed call just as it
did before, and return ``NOT_DONE_YET`` likewise. However, it
will also use ``Request.notifyFinish`` to make
sure ``_responseFailed`` is called if appropriate.





.. code-block:: python

    
    ...
        def render_GET(self, request):
            call = reactor.callLater(5, self._delayedRender, request)
            request.notifyFinish().addErrback(self._responseFailed, call)
            return NOT_DONE_YET




Notice that since ``_responseFailed`` needs a reference to
the delayed call object in order to cancel it, we passed that object
to ``addErrback`` . Any additional arguments passed
to ``addErrback`` (or ``addCallback`` ) will be
passed along to the errback after the :api:`twisted.python.failure.Failure <Failure>` instance which is always
passed as the first argument. Passing ``call`` here means it
will be passed to ``_responseFailed`` , where it is expected
and required.




That covers almost all the code for this example. Here's the entire example
without interruptions, as an :doc:`rpy script <rpy-scripts>` :





.. code-block:: python

    
    from twisted.web.resource import Resource
    from twisted.web.server import NOT_DONE_YET
    from twisted.internet import reactor
    
    class DelayedResource(Resource):
        def _delayedRender(self, request):
            request.write("<html><body>Sorry to keep you waiting.</body></html>")
            request.finish()
    
        def _responseFailed(self, err, call):
            call.cancel()
    
        def render_GET(self, request):
            call = reactor.callLater(5, self._delayedRender, request)
            request.notifyFinish().addErrback(self._responseFailed, call)
            return NOT_DONE_YET
    
    resource = DelayedResource()




Toss this into ``example.rpy`` , fire it up with ``twistd -n web --path .`` , and
hit `http://localhost:8080/example.rpy <http://localhost:8080/example.rpy>`_ . If
you wait five seconds, you'll get the page content. If you interrupt the request
before then, say by hitting escape (in Firefox, at least), then you'll see
perhaps the most boring demonstration ever - no page content, and nothing in the
server logs. Success!



