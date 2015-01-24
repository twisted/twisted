
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Generating a Page Dynamically
=============================





The goal of this example is to show you how to dynamically generate the
contents of a page.




Taking care of some of the necessary imports first, we'll import :api:`twisted.web.server.Site <Site>` and the :api:`twisted.internet.reactor <reactor>` :





.. code-block:: python

    
    from twisted.internet import reactor
    from twisted.web.server import Site




The Site is a factory which associates a listening port with the HTTP
protocol implementation. The reactor is the main loop that drives any Twisted
application; we'll use it to actually create the listening port in a moment.




Next, we'll import one more thing from Twisted
Web: :api:`twisted.web.resource.Resource <Resource>` . An
instance of ``Resource`` (or a subclass) represents a page
(technically, the entity addressed by a URI).





.. code-block:: python

    
    from twisted.web.resource import Resource




Since we're going to make the demo resource a clock, we'll also import the
time module:





.. code-block:: python

    
    import time




With imports taken care of, the next step is to define
a ``Resource`` subclass which has the dynamic rendering
behavior we want. Here's a resource which generates a page giving the
time:





.. code-block:: python

    
    class ClockPage(Resource):
        isLeaf = True
        def render_GET(self, request):
            return "<html><body>%s</body></html>" % (time.ctime(),)




Setting ``isLeaf`` to ``True`` indicates
that ``ClockPage`` resources will never have any
children.




The ``render_GET`` method here will be called whenever the URI we
hook this resource up to is requested with the ``GET`` method. The byte
string it returns is what will be sent to the browser.




With the resource defined, we can create a ``Site`` from it:





.. code-block:: python

    
    resource = ClockPage()
    factory = Site(resource)




Just as with the previous static content example, this
configuration puts our resource at the very top of the URI hierarchy,
ie at ``/`` . With that ``Site`` instance, we can
tell the reactor to :doc:`create a TCP server <../../../core/howto/servers>` and start servicing requests:





.. code-block:: python

    
    reactor.listenTCP(8880, factory)
    reactor.run()




Here's the code with no interruptions:





.. code-block:: python

    
    from twisted.internet import reactor
    from twisted.web.server import Site
    from twisted.web.resource import Resource
    import time
    
    class ClockPage(Resource):
        isLeaf = True
        def render_GET(self, request):
            return "<html><body>%s</body></html>" % (time.ctime(),)
    
    resource = ClockPage()
    factory = Site(resource)
    reactor.listenTCP(8880, factory)
    reactor.run()



