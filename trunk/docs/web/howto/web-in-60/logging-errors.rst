
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Logging Errors
==============





The :doc:`previous example <interrupted>` created a server that
dealt with response errors by aborting response generation, potentially avoiding
pointless work. However, it did this silently for any error. In this example,
we'll modify the previous example so that it logs each failed response.




This example will use the Twisted API for logging errors. As was
mentioned in the :doc:`first example covering Deferreds <asynchronous-deferred>` , errbacks are passed an error. In the previous
example, the ``_responseFailed`` errback accepted this error
as a parameter but ignored it. The only way this example will differ
is that this ``_responseFailed`` will use that error
parameter to log a message.




This example will require all of the imports required by the previous example
plus one new import:





.. code-block:: python

    
    from twisted.python.log import err




The only other part of the previous example which changes is
the ``_responseFailed`` callback, which will now log the
error passed to it:





.. code-block:: python

    
    ...
        def _responseFailed(self, failure, call):
            call.cancel()
            err(failure, "Async response demo interrupted response")




We're passing two arguments to :api:`twisted.python.log.err <err>` here. The first is the error which is being
passed in to the callback. This is always an object of type :api:`twisted.python.failure.Failure <Failure>` , a class which represents an
exception and (sometimes, but not always) a traceback. ``err`` will
format this nicely for the log. The second argument is a descriptive string that
tells someone reading the log what the source of the error was.




Here's the full example with the two above modifications:





.. code-block:: python

    
    from twisted.web.resource import Resource
    from twisted.web.server import NOT_DONE_YET
    from twisted.internet import reactor
    from twisted.python.log import err
    
    class DelayedResource(Resource):
        def _delayedRender(self, request):
            request.write("<html><body>Sorry to keep you waiting.</body></html>")
            request.finish()
    
        def _responseFailed(self, failure, call):
            call.cancel()
            err(failure, "Async response demo interrupted response")
    
        def render_GET(self, request):
            call = reactor.callLater(5, self._delayedRender, request)
            request.notifyFinish().addErrback(self._responseFailed, call)
            return NOT_DONE_YET
    
    resource = DelayedResource()




Run this server as in the :doc:`previous example <interrupted>` 
and interrupt a request. Unlike the previous example, where the server gave no
indication that this had happened, you'll see a message in the log output with
this version.



