
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Asynchronous Responses (via Deferred)
=====================================





The previous example had a :api:`twisted.web.resource.Resource <Resource>` that generates its response
asynchronously rather than immediately upon the call to its render
method. Though it was a useful demonstration of the ``NOT_DONE_YET`` 
feature of Twisted Web, the example didn't reflect what a realistic application
might want to do. This example introduces :api:`twisted.internet.defer.Deferred <Deferred>` , the Twisted class which is used
to provide a uniform interface to many asynchronous events, and shows you an
example of using a ``Deferred`` -returning API to generate an
asynchronous response to a request in Twisted Web.




``Deferred`` is the result of two consequences of the
asynchronous programming approach. First, asynchronous code is
frequently (if not always) concerned with some data (in Python, an
object) which is not yet available but which probably will be
soon. Asynchronous code needs a way to define what will be done to the
object once it does exist. It also needs a way to define how to handle
errors in the creation or acquisition of that object. These two needs
are satisfied by the *callbacks* and *errbacks* of
a ``Deferred`` . Callbacks are added to
a ``Deferred`` with :api:`twisted.internet.defer.Deferred.addCallback <Deferred.addCallback>` ; errbacks
are added with :api:`twisted.internet.defer.Deferred.addErrback <Deferred.addErrback>` . When the
object finally does exist, it is passed to :api:`twisted.internet.defer.Deferred.callback <Deferred.callback>` which passes it
on to the callback added with ``addCallback`` . Similarly, if
an error occurs, :api:`twisted.internet.defer.Deferred.errback <Deferred.errback>` is called and
the error is passed along to the errback added
with ``addErrback`` . Second, the events that make
asynchronous code actually work often take many different,
incompatible forms. ``Deferred`` acts as the uniform
interface which lets different parts of an asynchronous application
interact and isolates them from implementation details they shouldn't
be concerned with.




That's almost all there is to ``Deferred`` . To solidify your new
understanding, now consider this rewritten version
of ``DelayedResource`` which uses a ``Deferred`` -based delay
API. It does exactly the same thing as the :doc:`previous example <asynchronous>` . Only the implementation is different.




First, the example must import that new API that was just mentioned, :api:`twisted.internet.task.deferLater <deferLater>` :





.. code-block:: python

    
    from twisted.internet.task import deferLater




Next, all the other imports (these are the same as last time):





.. code-block:: python

    
    from twisted.web.resource import Resource
    from twisted.web.server import NOT_DONE_YET
    from twisted.internet import reactor




With the imports done, here's the first part of
the ``DelayedResource`` implementation. Again, this part of
the code is identical to the previous version:





.. code-block:: python

    
    class DelayedResource(Resource):
        def _delayedRender(self, request):
            request.write("<html><body>Sorry to keep you waiting.</body></html>")
            request.finish()




Next we need to define the render method. Here's where things
change a bit. Instead of using :api:`twisted.internet.interfaces.IReactorTime.callLater <callLater>` ,
We're going to use :api:`twisted.internet.task.deferLater <deferLater>` this
time. ``deferLater`` accepts a reactor, delay (in seconds, as
with ``callLater`` ), and a function to call after the delay
to produce that elusive object discussed in the description
of ``Deferred`` s. We're also going to
use ``_delayedRender`` as the callback to add to
the ``Deferred`` returned by ``deferLater`` . Since
it expects the request object as an argument, we're going to set up
the ``deferLater`` call to return a ``Deferred`` 
which has the request object as its result.





.. code-block:: python

    
    ...
        def render_GET(self, request):
            d = deferLater(reactor, 5, lambda: request)




The ``Deferred`` referenced by ``d`` now needs to
have the ``_delayedRender`` callback added to it. Once this
is done, ``_delayedRender`` will be called with the result
of ``d`` (which will be ``request`` , of course — the
result of ``(lambda: request)()`` ).





.. code-block:: python

    
    ...
            d.addCallback(self._delayedRender)




Finally, the render method still needs to return ``NOT_DONE_YET`` ,
for exactly the same reasons as it did in the previous version of the
example.





.. code-block:: python

    
    ...
            return NOT_DONE_YET




And with that, ``DelayedResource`` is now implemented
based on a ``Deferred`` . The example still isn't very
realistic, but remember that since ``Deferred`` s offer a
uniform interface to many different asynchronous event sources, this
code now resembles a real application even more closely; you could
easily replace ``deferLater`` with
another ``Deferred`` -returning API and suddenly you might
have a resource that does something useful.




Finally, here's the complete, uninterrupted example source, as an rpy script:





.. code-block:: python

    
    from twisted.internet.task import deferLater
    from twisted.web.resource import Resource
    from twisted.web.server import NOT_DONE_YET
    from twisted.internet import reactor
    
    class DelayedResource(Resource):
        def _delayedRender(self, request):
            request.write("<html><body>Sorry to keep you waiting.</body></html>")
            request.finish()
    
        def render_GET(self, request):
            d = deferLater(reactor, 5, lambda: request)
            d.addCallback(self._delayedRender)
            return NOT_DONE_YET
    
    resource = DelayedResource()



