
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Error Handling
==============





In this example we'll extend dynamic dispatch to return a 404 (not found)
response when a client requests a non-existent URL.




As in the previous examples, we'll start with :api:`twisted.web.server.Site <Site>` , :api:`twisted.web.resource.Resource <Resource>` , and :api:`twisted.internet.reactor <reactor>` imports:





.. code-block:: python

    
    from twisted.web.server import Site
    from twisted.web.resource import Resource
    from twisted.internet import reactor




Next, we'll add one more import. :api:`twisted.web.resource.NoResource <NoResource>` is one of the pre-defined error
resources provided by Twisted Web. It generates the necessary 404 response code
and renders a simple html page telling the client there is no such resource.





.. code-block:: python

    
    from twisted.web.resource import NoResource




Next, we'll define a custom resource which does some dynamic URL
dispatch. This example is going to be just like
the :doc:`previous one <dynamic-dispatch>` , where the path segment is
interpreted as a year; the difference is that this time we'll handle requests
which don't conform to that pattern by returning the not found response:





.. code-block:: python

    
    class Calendar(Resource):
        def getChild(self, name, request):
            try:
                year = int(name)
            except ValueError:
                return NoResource()
            else:
                return YearPage(year)




Aside from including the definition of ``YearPage`` from
the previous example, the only other thing left to do is the
normal ``Site`` and ``reactor`` setup. Here's the
complete code for this example:





.. code-block:: python

    
    from twisted.web.server import Site
    from twisted.web.resource import Resource
    from twisted.internet import reactor
    from twisted.web.resource import NoResource
    
    from calendar import calendar
    
    class YearPage(Resource):
        def __init__(self, year):
            Resource.__init__(self)
            self.year = year
    
        def render_GET(self, request):
            return "<html><body><pre>%s</pre></body></html>" % (calendar(self.year),)
    
    class Calendar(Resource):
        def getChild(self, name, request):
            try:
                year = int(name)
            except ValueError:
                return NoResource()
            else:
                return YearPage(year)
    
    root = Calendar()
    factory = Site(root)
    reactor.listenTCP(8880, factory)
    reactor.run()




This server hands out the same calendar views as the one from the previous
installment, but it will also hand out a nice error page with a 404 response
when a request is made for a URL which cannot be interpreted as a year.



