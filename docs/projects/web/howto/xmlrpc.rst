
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Creating XML-RPC Servers and Clients with Twisted
=================================================






Introduction
------------



`XML-RPC <http://www.xmlrpc.com>`_ is a simple request/reply protocol
that runs over HTTP. It is simple, easy to implement and supported by most programming
languages. Twisted's XML-RPC support is implemented using the`xmlrpclib <http://docs.python.org/library/xmlrpclib.html>`_ library that is
included with Python 2.2 and later.





Creating a XML-RPC server
-------------------------



Making a server is very easy - all you need to do is inherit from :api:`twisted.web.xmlrpc.XMLRPC <twisted.web.xmlrpc.XMLRPC>` .
You then create methods beginning with ``xmlrpc_`` . The methods'
arguments determine what arguments it will accept from XML-RPC clients.
The result is what will be returned to the clients.




Methods published via XML-RPC can return all the basic XML-RPC
types, such as strings, lists and so on (just return a regular python
integer, etc).  They can also raise exceptions or return Failure instances to indicate an
error has occurred, or ``Binary`` , ``Boolean`` or ``DateTime`` 
instances (all of these are the same as the respective classes in xmlrpclib. In
addition, XML-RPC published methods can return :api:`twisted.internet.defer.Deferred <Deferred>` instances whose results are one of the above. This allows
you to return results that can't be calculated immediately, such as database queries.
See the :doc:`Deferred documentation <../../core/howto/defer>` for more
details.




:api:`twisted.web.xmlrpc.XMLRPC <XMLRPC>` instances
are Resource objects, and they can thus be published using a Site. The
following example has two methods published via XML-RPC, ``add(a, b)`` and ``echo(x)`` .





.. code-block:: python

    
    from twisted.web import xmlrpc, server
    
    class Example(xmlrpc.XMLRPC):
        """
        An example object to be published.
        """
    
        def xmlrpc_echo(self, x):
            """
            Return all passed args.
            """
            return x
    
        def xmlrpc_add(self, a, b):
            """
            Return sum of arguments.
            """
            return a + b
    
        def xmlrpc_fault(self):
            """
            Raise a Fault indicating that the procedure should not be used.
            """
            raise xmlrpc.Fault(123, "The fault procedure is faulty.")
    
    if __name__ == '__main__':
        from twisted.internet import reactor
        r = Example()
        reactor.listenTCP(7080, server.Site(r))
        reactor.run()




After we run this command, we can connect with a client and send commands
to the server:





.. code-block:: pycon

    
    >>> import xmlrpclib
    >>> s = xmlrpclib.Server('http://localhost:7080/')
    >>> s.echo("lala")
    'lala'
    >>> s.add(1, 2)
    3
    >>> s.fault()
    Traceback (most recent call last):
    ...
    xmlrpclib.Fault: <Fault 123: 'The fault procedure is faulty.'>
    >>>
    




If the :api:`twisted.web.server.Request <Request>` object is
needed by an ``xmlrpc_*`` method, it can be made available using
the :api:`twisted.web.xmlrpc.withRequest <twisted.web.xmlrpc.withRequest>` decorator.  When
using this decorator, the method will be passed the request object as the first
argument, before any XML-RPC parameters.  For example:





.. code-block:: python

    
    from twisted.web.xmlrpc import XMLRPC, withRequest
    from twisted.web.server import Site
    
    class Example(XMLRPC):
        @withRequest
        def xmlrpc_headerValue(self, request, headerName):
            return request.requestHeaders.getRawHeaders(headerName)
    
    if __name__ == '__main__':
        from twisted.internet import reactor
        reactor.listenTCP(7080, Site(Example()))
        reactor.run()




XML-RPC resources can also be part of a normal Twisted web server, using
resource scripts. The following is an example of such a resource script:





:download:`xmlquote.rpy <listings/xmlquote.rpy>`

.. literalinclude:: listings/xmlquote.rpy



Using XML-RPC sub-handlers
~~~~~~~~~~~~~~~~~~~~~~~~~~



XML-RPC resource can be nested so that one handler calls another if
a method with a given prefix is called. For example, to add support
for an XML-RPC method ``date.time()`` to
the ``Example`` class, you could do the
following:





.. code-block:: python

    
    import time
    from twisted.web import xmlrpc, server
    
    class Example(xmlrpc.XMLRPC):
        """
        An example object to be published.
        """
    
        def xmlrpc_echo(self, x):
            """
            Return all passed args.
            """
            return x
    
        def xmlrpc_add(self, a, b):
            """
            Return sum of arguments.
            """
            return a + b
    
    class Date(xmlrpc.XMLRPC):
        """
        Serve the XML-RPC 'time' method.
        """
    
        def xmlrpc_time(self):
            """
            Return UNIX time.
            """
            return time.time()
    
    if __name__ == '__main__':
        from twisted.internet import reactor
        r = Example()
        date = Date()
        r.putSubHandler('date', date)
        reactor.listenTCP(7080, server.Site(r))
        reactor.run()




By default, a period ('.') separates the prefix from the method
name, but you can use a different character by overriding the ``XMLRPC.separator`` data member in your base
XML-RPC server. XML-RPC servers may be nested to arbitrary depths
using this method.





Using your own procedure getter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



Sometimes, you want to implement your own policy of getting the end implementation.
E.g. just like sub-handlers you want to divide the implementations into separate classes but
may not want to introduce ``XMLRPC.separator`` in the procedure name.
In such cases just override the ``lookupProcedure(self, procedurePath)`` 
method and return the correct callable.
Raise :api:`twisted.web.xmlrpc.NoSuchFunction <twisted.web.xmlrpc.NoSuchFunction>` otherwise.





:download:`xmlrpc-customized.py <listings/xmlrpc-customized.py>`

.. literalinclude:: listings/xmlrpc-customized.py



Adding XML-RPC Introspection support
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



XML-RPC has an
informal `IntrospectionAPI <http://tldp.org/HOWTO/XML-RPC-HOWTO/xmlrpc-howto-interfaces.html>`_ that specifies three methods in a ``system`` 
sub-handler which allow a client to query a server about the server's
API. Adding Introspection support to
the ``Example`` class is easy using
the :api:`twisted.web.xmlrpc.XMLRPCIntrospection <XMLRPCIntrospection>` class:





.. code-block:: python

    
    from twisted.web import xmlrpc, server
    
    class Example(xmlrpc.XMLRPC):
        """An example object to be published."""
    
        def xmlrpc_echo(self, x):
            """Return all passed args."""
            return x
    
        xmlrpc_echo.signature = [['string', 'string'],
                                 ['int', 'int'],
                                 ['double', 'double'],
                                 ['array', 'array'],
                                 ['struct', 'struct']]
    
        def xmlrpc_add(self, a, b):
            """Return sum of arguments."""
            return a + b
    
        xmlrpc_add.signature = [['int', 'int', 'int'],
                                ['double', 'double', 'double']]
        xmlrpc_add.help = "Add the arguments and return the sum."
    
    if __name__ == '__main__':
        from twisted.internet import reactor
        r = Example()
        xmlrpc.addIntrospection(r)
        reactor.listenTCP(7080, server.Site(r))
        reactor.run()




Note the method attributes ``help`` 
and ``signature`` which are used by the
Introspection API methods ``system.methodHelp`` 
and ``system.methodSignature`` respectively. If
no ``help`` attribute is specified, the
method's documentation string is used instead.





SOAP Support
------------



From the point of view of a Twisted developer, there is little difference
between XML-RPC support and SOAP support. Here is an example of SOAP usage:





:download:`soap.rpy <listings/soap.rpy>`

.. literalinclude:: listings/soap.rpy



Creating an XML-RPC Client
--------------------------



XML-RPC clients in Twisted are meant to look as something which will be
familiar either to ``xmlrpclib`` or to Perspective Broker users,
taking features from both, as appropriate. There are two major deviations
from the ``xmlrpclib`` way which should be noted:





#. No implicit ``/RPC2`` . If the services uses this path for the
   XML-RPC calls, then it will have to be given explicitly.
#. No magic ``__getattr__`` : calls must be made by an explicit
   ``callRemote`` .



The interface Twisted presents to XML-RPC client is that of a proxy
object: :api:`twisted.web.xmlrpc.Proxy <twisted.web.xmlrpc.Proxy>` . The
constructor for the object receives a URL: it must be an HTTP or HTTPS
URL. When an XML-RPC service is described, the URL to that service
will be given there.




Having a proxy object, one can just call the ``callRemote`` method,
which accepts a method name and a variable argument list (but no named
arguments, as these are not supported by XML-RPC). It returns a deferred,
which will be called back with the result. If there is any error, at any
level, the errback will be called. The exception will be the relevant Twisted
error in the case of a problem with the underlying connection (for example,
a timeout), ``IOError`` containing the status and message in the case
of a non-200 status or a ``xmlrpclib.Fault`` in the case of an
XML-RPC level problem.





.. code-block:: python

    
    from twisted.web.xmlrpc import Proxy
    from twisted.internet import reactor
    
    def printValue(value):
        print repr(value)
        reactor.stop()
    
    def printError(error):
        print 'error', error
        reactor.stop()
    
    proxy = Proxy('http://advogato.org/XMLRPC')
    proxy.callRemote('test.sumprod', 3, 5).addCallbacks(printValue, printError)
    reactor.run()




prints:





::

    
    [8, 15]





Serving SOAP and XML-RPC simultaneously
---------------------------------------



:api:`twisted.web.xmlrpc.XMLRPC <twisted.web.xmlrpc.XMLRPC>` and :api:`twisted.web.soap.SOAPPublisher <twisted.web.soap.SOAPPublisher>` are both :api:`twisted.web.resource.Resource <Resource>` s.  So, to serve both XML-RPC and
SOAP in the one web server, you can use the :api:`twisted.web.resource.IResource.putChild <putChild>` method of Resource.




The following example uses an empty :api:`twisted.web.resource.Resource <resource.Resource>` as the root resource for
a :api:`twisted.web.server.Site <Site>` , and then
adds ``/RPC2`` and ``/SOAP`` paths to it.





:download:`xmlAndSoapQuote.py <listings/xmlAndSoapQuote.py>`

.. literalinclude:: listings/xmlAndSoapQuote.py


Refer to :ref:`Twisted Web
Development <web-howto-using-twistedweb-development>` for more details about Resources.

  

