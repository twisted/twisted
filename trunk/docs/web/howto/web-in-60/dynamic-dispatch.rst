
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Dynamic URL Dispatch
====================





In the :doc:`previous example <static-dispatch>` we covered how to
statically configure Twisted Web to serve different content at different
URLs. The goal of this example is to show you how to do this dynamically
instead. Reading the previous installment if you haven't already is suggested in
order to get an overview of how URLs are treated when using Twisted Web's :api:`twisted.web.resource <resource>` APIs.




:api:`twisted.web.server.Site <Site>` (the object which
associates a listening server port with the HTTP implementation), :api:`twisted.web.resource.Resource <Resource>` (a convenient base class
to use when defining custom pages), and :api:`twisted.internet.reactor <reactor>` (the object which implements the Twisted
main loop) return once again:





.. code-block:: python

    
    from twisted.web.server import Site
    from twisted.web.resource import Resource
    from twisted.internet import reactor




With that out of the way, here's the interesting part of this
example. We're going to define a resource which renders a whole-year
calendar. The year it will render the calendar for will be the year in
the request URL. So, for example, ``/2009`` will render a
calendar for 2009. First, here's a resource that renders a calendar
for the year passed to its initializer:





.. code-block:: python

    
    from calendar import calendar
    
    class YearPage(Resource):
        def __init__(self, year):
            Resource.__init__(self)
            self.year = year
    
        def render_GET(self, request):
            return "<html><body><pre>%s</pre></body></html>" % (calendar(self.year),)




Pretty simple - not all that different from the first dynamic resource
demonstrated in :doc:`Generating a Page Dynamically <dynamic-content>` . Now here's the resource that handles URLs with a year in them
by creating a suitable instance of this ``YearPage`` class:





.. code-block:: python

    
    class Calendar(Resource):
      def getChild(self, name, request):
          return YearPage(int(name))




By implementing :api:`twisted.web.resource.Resource.getChild <getChild>` here, we've just defined
how Twisted Web should find children of ``Calendar`` instances when
it's resolving an URL into a resource. This implementation defines all integers
as the children of ``Calendar`` (and punts on error handling, more on
that later).




All that's left is to create a ``Site`` using this resource as its
root and then start the reactor:





::

    
    root = Calendar()
    factory = Site(root)
    reactor.listenTCP(8880, factory)
    reactor.run()




And that's all. Any resource-based dynamic URL handling is going to look
basically like ``Calendar.getChild`` . Here's the full example code:





.. code-block:: python

    
    from twisted.web.server import Site
    from twisted.web.resource import Resource
    from twisted.internet import reactor
    
    from calendar import calendar
    
    class YearPage(Resource):
        def __init__(self, year):
            Resource.__init__(self)
            self.year = year
    
        def render_GET(self, request):
            return "<html><body><pre>%s</pre></body></html>" % (calendar(self.year),)
    
    class Calendar(Resource):
      def getChild(self, name, request):
          return YearPage(int(name))
    
    root = Calendar()
    factory = Site(root)
    reactor.listenTCP(8880, factory)
    reactor.run()




