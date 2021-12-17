
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Static URL Dispatch
===================





The goal of this example is to show you how to serve different content at
different URLs.




The key to understanding how different URLs are handled with the resource
APIs in Twisted Web is understanding that any URL can be used to address a node
in a tree. Resources in Twisted Web exist in such a tree, and a request for a
URL will be responded to by the resource which that URL addresses. The
addressing scheme considers only the path segments of the URL. Starting with the
root resource (the one used to construct the ``Site`` ) and the first
path segment, a child resource is looked up. As long as there are more path
segments, this process is repeated using the result of the previous lookup and
the next path segment. For example, to handle a request
for ``"/foo/bar"`` , first the root's ``"foo"`` child is
retrieved, then that resource's ``"bar"`` child is retrieved, then that
resource is used to create the response.




With that out of the way, let's consider an example that can serve a few
different resources at a few different URLs.




First things first: we need to import :py:class:`Site <twisted.web.server.Site>` , the factory for HTTP servers, :py:class:`Resource <twisted.web.resource.Resource>` , a convenient base class
for custom pages, :py:mod:`reactor <twisted.internet.reactor>` ,
the object which implements the Twisted main loop, and :py:mod:`endpoints <twisted.internet.endpoints>`, which contains classes for creating listening sockets. We'll also import :py:class:`File <twisted.web.static.File>` to use as the resource at one
of the example URLs.





.. code-block:: python


    from twisted.web.server import Site
    from twisted.web.resource import Resource
    from twisted.internet import reactor, endpoints
    from twisted.web.static import File




Now we create a resource which will correspond to the root of the URL
hierarchy: all URLs are children of this resource.





.. code-block:: python


    root = Resource()




Here comes the interesting part of this example. We're now going to
create three more resources and attach them to the three
URLs ``/foo`` , ``/bar`` , and ``/baz`` :





.. code-block:: python


    root.putChild(b"foo", File("/tmp"))
    root.putChild(b"bar", File("/lost+found"))
    root.putChild(b"baz", File("/opt"))




Last, all that's required is to create a ``Site`` with the root
resource, associate it with a listening server port, and start the reactor:





.. code-block:: python


    factory = Site(root)
    endpoint = endpoints.TCP4ServerEndpoint(reactor, 8880)
    endpoint.listen(factory)
    reactor.run()




With this server running, ``http://localhost:8880/foo``
will serve a listing of files
from ``/tmp`` , ``http://localhost:8880/bar`` will
serve a listing of files from ``/lost+found`` ,
and ``http://localhost:8880/baz`` will serve a listing of
files from ``/opt`` .




Here's the whole example uninterrupted:





.. code-block:: python


    from twisted.web.server import Site
    from twisted.web.resource import Resource
    from twisted.internet import reactor, endpoints
    from twisted.web.static import File

    root = Resource()
    root.putChild(b"foo", File("/tmp"))
    root.putChild(b"bar", File("/lost+found"))
    root.putChild(b"baz", File("/opt"))

    factory = Site(root)
    endpoint = endpoints.TCP4ServerEndpoint(reactor, 8880)
    endpoint.listen(factory)
    reactor.run()



