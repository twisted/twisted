
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Using the Twisted Web Client
============================






Overview
--------


    

This document describes how to use the HTTP client included in Twisted
Web.  After reading it, you should be able to make HTTP and HTTPS
requests using Twisted Web.  You will be able to specify the request
method, headers, and body and you will be able to retrieve the response
code, headers, and body.


    



A number of higher-level features are also explained, including proxying,
automatic content encoding negotiation, and cookie handling.


    



Prerequisites
~~~~~~~~~~~~~


    


This document assumes that you are familiar with :doc:`Deferreds and Failures <../../core/howto/defer>` , and :doc:`producers and consumers <../../core/howto/producers>` .
It also assumes you are familiar with the basic concepts of HTTP, such
as requests and responses, methods, headers, and message bodies.  The
HTTPS section of this document also assumes you are somewhat familiar with
SSL and have read about :doc:`using SSL in Twisted <../../core/howto/ssl>` .


    



The Agent
---------


    

Issuing Requests
~~~~~~~~~~~~~~~~


    

The :api:`twisted.web.client.Agent <twisted.web.client.Agent>` class is the entry
point into the client API.  Requests are issued using the :api:`twisted.web.client.Agent.request <request>` method, which
takes as parameters a request method, a request URI, the request headers,
and an object which can produce the request body (if there is to be one).
The agent is responsible for connection setup.  Because of this, it
requires a reactor as an argument to its initializer.  An example of
creating an agent and issuing a request using it might look like this:


    



:download:`request.py <listings/client/request.py>`

.. literalinclude:: listings/client/request.py



As may be obvious, this issues a new *GET* request for */* 
to the web server on ``example.com`` .  ``Agent`` is
responsible for resolving the hostname into an IP address and connecting
to it on port 80 (for *HTTP* URIs), port 443 (for *HTTPS* 
URIs), or on the port number specified in the URI itself.  It is also
responsible for cleaning up the connection afterwards.  This code sends
a request which includes one custom header, *User-Agent* .  The
last argument passed to ``Agent.request`` is ``None`` ,
though, so the request has no body.


    



Sending a request which does include a body requires passing an object
providing :api:`twisted.web.iweb.IBodyProducer <twisted.web.iweb.IBodyProducer>` 
to ``Agent.request`` .  This interface extends the more general
:api:`twisted.internet.interfaces.IPushProducer <IPushProducer>` 
by adding a new ``length`` attribute and adding several
constraints to the way the producer and consumer interact.


    




- 
  The length attribute must be a non-negative integer or the constant
  ``twisted.web.iweb.UNKNOWN_LENGTH`` .  If the length is known,
  it will be used to specify the value for the
  *Content-Length* header in the request.  If the length is
  unknown the attribute should be set to ``UNKNOWN_LENGTH`` .
  Since more servers support *Content-Length* , if a length can be
  provided it should be.
- 
  An additional method is required on ``IBodyProducer`` 
  implementations: ``startProducing`` .  This method is used to
  associate a consumer with the producer.  It should return a
  ``Deferred`` which fires when all data has been produced.
- 
  ``IBodyProducer`` implementations should never call the
  consumer's ``unregisterProducer`` method.  Instead, when it
  has produced all of the data it is going to produce, it should only
  fire the ``Deferred`` returned by ``startProducing`` .


    



For additional details about the requirements of :api:`twisted.web.iweb.IBodyProducer <IBodyProducer>` implementations, see
the API documentation.


    



Here's a simple ``IBodyProducer`` implementation which
writes an in-memory string to the consumer:


    



:download:`stringprod.py <listings/client/stringprod.py>`

.. literalinclude:: listings/client/stringprod.py



This producer can be used to issue a request with a body:


    



:download:`sendbody.py <listings/client/sendbody.py>`

.. literalinclude:: listings/client/sendbody.py



If you want to upload a file or you just have some data in a string, you
don't have to copy ``StringProducer`` though.  Instead, you can
use :api:`twisted.web.client.FileBodyProducer <FileBodyProducer>` .
This ``IBodyProducer`` implementation works with any file-like
object (so use it with a ``StringIO`` if your upload data is
already in memory as a string); the idea is the same
as ``StringProducer`` from the previous example, but with a
little extra code to only send data as fast as the server will take it.


    



:download:`filesendbody.py <listings/client/filesendbody.py>`

.. literalinclude:: listings/client/filesendbody.py



``FileBodyProducer`` closes the file when it no longer needs it.


    



If the connection or the request take too much time, you can cancel the
``Deferred`` returned by the ``Agent.request`` method.
This will abort the connection, and the ``Deferred`` will errback
with :api:`twisted.internet.defer.CancelledError <CancelledError>` .


    



Receiving Responses
~~~~~~~~~~~~~~~~~~~


    

So far, the examples have demonstrated how to issue a request.  However,
they have ignored the response, except for showing that it is a
``Deferred`` which seems to fire when the response has been
received.  Next we'll cover what that response is and how to interpret
it.


    



``Agent.request`` , as with most ``Deferred`` -returning
APIs, can return a ``Deferred`` which fires with a
``Failure`` .  If the request fails somehow, this will be
reflected with a failure.  This may be due to a problem looking up the
host IP address, or it may be because the HTTP server is not accepting
connections, or it may be because of a problem parsing the response, or
any other problem which arises which prevents the response from being
received.  It does *not* include responses with an error status.


    



If the request succeeds, though, the ``Deferred`` will fire with
a :api:`twisted.web.client.Response <Response>` .  This
happens as soon as all the response headers have been received.  It
happens before any of the response body, if there is one, is processed.
The ``Response`` object has several attributes giving the
response information: its code, version, phrase, and headers, as well as
the length of the body to expect. In addition to these, the
``Response`` also contains a reference to the :api:`twisted.web.iweb.IClientRequest.request <request>` that it is
a response to; one particularly useful attribute on the request is :api:`twisted.web.iweb.IClientRequest.absoluteURI <absoluteURI>` :
The absolute URI to which the request was made.  The
``Response`` object has a method which makes the response body
available: :api:`twisted.web.client.Response.deliverBody <deliverBody>` .  Using the
attributes of the response object and this method, here's an example
which displays part of the response to a request:


    



:download:`response.py <listings/client/response.py>`

.. literalinclude:: listings/client/response.py



The ``BeginningPrinter`` protocol in this example is passed to
``Response.deliverBody`` and the response body is then delivered
to its ``dataReceived`` method as it arrives.  When the body has
been completely delivered, the protocol's ``connectionLost`` 
method is called.  It is important to inspect the ``Failure`` 
passed to ``connectionLost`` .  If the response body has been
completely received, the failure will wrap a :api:`twisted.web.client.ResponseDone <twisted.web.client.ResponseDone>` exception.  This
indicates that it is *known* that all data has been received.  It
is also possible for the failure to wrap a :api:`twisted.web.http.PotentialDataLoss <twisted.web.http.PotentialDataLoss>` exception: this
indicates that the server framed the response such that there is no way
to know when the entire response body has been received.  Only
HTTP/1.0 servers should behave this way.  Finally, it is possible for
the exception to be of another type, indicating guaranteed data loss for
some reason (a lost connection, a memory error, etc).


    



Just as protocols associated with a TCP connection are given a transport,
so will be a protocol passed to ``deliverBody`` .  Since it makes
no sense to write more data to the connection at this stage of the
request, though, the transport *only* provides :api:`twisted.internet.interfaces.IPushProducer <IPushProducer>` .  This allows the
protocol to control the flow of the response data: a call to the
transport's ``pauseProducing`` method will pause delivery; a
later call to ``resumeProducing`` will resume it.  If it is
decided that the rest of the response body is not desired,
``stopProducing`` can be used to stop delivery permanently;
after this, the protocol's ``connectionLost`` method will be
called.


    



An important thing to keep in mind is that the body will only be read
from the connection after ``Response.deliverBody`` is called.
This also means that the connection will remain open until this is done
(and the body read).  So, in general, any response with a body
*must* have that body read using ``deliverBody`` .  If the
application is not interested in the body, it should issue a
*HEAD* request or use a protocol which immediately calls
``stopProducing`` on its transport.


    



If the body of the response isn't going to be consumed incrementally, then :api:`twisted.web.client.readBody <readBody>` can be used to get the body as a byte-string.
This function returns a ``Deferred`` that fires with the body after the request has been completed; cancelling this ``Deferred`` will close the connection to the HTTP server immediately.


    



:download:`responseBody.py <listings/client/responseBody.py>`

.. literalinclude:: listings/client/responseBody.py



HTTP over SSL
~~~~~~~~~~~~~


    

Everything you've read so far applies whether the scheme of the request
URI is *HTTP* or *HTTPS* .  However, to control the SSL
negotiation performed when an *HTTPS* URI is requested, there's
one extra object to pay attention to: the SSL context factory.


    



``Agent`` 's constructor takes an optional second argument, a
context factory.  This is an object like the context factory described
in :doc:`Using SSL in Twisted <../../core/howto/ssl>` but has
one small difference.  The ``getContext`` method of this factory
accepts the address from the URL being requested.  This allows it to
return a context object which verifies that the server's certificate
matches the URL being requested.


    



Here's an example which shows how to use ``Agent`` to request
an *HTTPS* URL with no certificate verification.


    



.. code-block:: python

    
    from twisted.python.log import err
    from twisted.web.client import Agent
    from twisted.internet import reactor
    from twisted.internet.ssl import ClientContextFactory
    
    class WebClientContextFactory(ClientContextFactory):
        def getContext(self, hostname, port):
            return ClientContextFactory.getContext(self)
    
    def display(response):
        print "Received response"
        print response
    
    def main():
        contextFactory = WebClientContextFactory()
        agent = Agent(reactor, contextFactory)
        d = agent.request("GET", "https://example.com/")
        d.addCallbacks(display, err)
        d.addCallback(lambda ignored: reactor.stop())
        reactor.run()
    
    if __name__ == "__main__":
        main()



    

The important point to notice here is that ``getContext`` now
accepts two arguments, a hostname and a port number.  These two arguments,
a ``str`` and an ``int`` , give the address to which a
connection is being established to request an HTTPS URL.  Because an agent
might make multiple requests over a single connection,
``getContext`` may not be called once for each request.  A second
or later request for a URL with the same hostname as a previous request
may re-use an existing connection, and therefore will re-use the
previously returned context object.


    



To configure SSL options or enable certificate verification or hostname
checking, provide a context factory which creates suitably configured
context objects.


    



HTTP Persistent Connection
~~~~~~~~~~~~~~~~~~~~~~~~~~


    

HTTP persistent connections use the same TCP connection to send and
receive multiple HTTP requests/responses. This reduces latency and TCP
connection establishment overhead.


    



The constructor of :api:`twisted.web.client.Agent <twisted.web.client.Agent>` 
takes an optional parameter pool, which should be an instance
of :api:`twisted.web.client.HTTPConnectionPool <HTTPConnectionPool>` , which will be used
to manage the connections.  If the pool is created with the
parameter ``persistent`` set to ``True`` (the
default), it will not close connections when the request is done, and
instead hold them in its cache to be re-used.


    



Here's an example which sends requests over a persistent connection:


    



.. code-block:: python

    
    from twisted.internet import reactor
    from twisted.internet.defer import Deferred, DeferredList
    from twisted.internet.protocol import Protocol
    from twisted.web.client import Agent, HTTPConnectionPool
    
    class IgnoreBody(Protocol):
        def __init__(self, deferred):
            self.deferred = deferred
    
        def dataReceived(self, bytes):
            pass
    
        def connectionLost(self, reason):
            self.deferred.callback(None)
    
    
    def cbRequest(response):
        print 'Response code:', response.code
        finished = Deferred()
        response.deliverBody(IgnoreBody(finished))
        return finished
    
    pool = HTTPConnectionPool(reactor)
    agent = Agent(reactor, pool=pool)
    
    def requestGet(url):
        d = agent.request('GET', url)
        d.addCallback(cbRequest)
        return d
    
    # Two requests to the same host:
    d = requestGet('http://localhost:8080/foo').addCallback(
        lambda ign: requestGet("http://localhost:8080/bar"))
    def cbShutdown(ignored):
        reactor.stop()
    d.addCallback(cbShutdown)
    
    reactor.run()



    

Here, the two requests are to the same host, one after the each
other. In most cases, the same connection will be used for the second
request, instead of two different connections when using a
non-persistent pool.


    



Multiple Connections to the Same Server
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


    

:api:`twisted.web.client.HTTPConnectionPool <twisted.web.client.HTTPConnectionPool>` instances
have an attribute
called ``maxPersistentPerHost`` which limits the
number of cached persistent connections to the same server. The default
value is 2.  This is effective only when the :api:`twisted.web.client.HTTPConnectionPool.persistent <persistent>` option is
True. You can change the value like bellow:


    



.. code-block:: python

    
    from twisted.web.client import HTTPConnectionPool
    
    pool = HTTPConnectionPool(reactor, persistent=True)
    pool.maxPersistentPerHost = 1



    

With the default value of 2, the pool keeps around two connections to
the same host at most. Eventually the cached persistent connections will
be closed, by default after 240 seconds; you can change this timeout
value with the ``cachedConnectionTimeout`` 
attribute of the pool. To force all connections to close use
the :api:`twisted.web.client.HTTPConnectionPool.closeCachedConnections <closeCachedConnections>` 
method.



    



Automatic Retries
^^^^^^^^^^^^^^^^^


    
If a request fails without getting a response, and the request is
something that hopefully can be retried without having any side-effects
(e.g. a request with method GET), it will be retried automatically when
sending a request over a previously-cached persistent connection. You can
disable this behavior by setting :api:`twisted.web.client.HTTPConnectionPool.retryAutomatically <retryAutomatically>` 
to ``False`` . Note that each request will only be retried
once.


    



Following redirects
~~~~~~~~~~~~~~~~~~~


    

By itself, ``Agent`` doesn't follow HTTP redirects (responses
with 301, 302, 303, 307 status codes and a ``location`` header
field). You need to use the :api:`twisted.web.client.RedirectAgent <twisted.web.client.RedirectAgent>` class to do so. It
implements a rather strict behavior of the RFC, meaning it will redirect
301 and 302 as 307, only on ``GET`` and ``HEAD`` 
requests.

    



The following example shows how to have a redirect-enabled agent.


    



.. code-block:: python

    
    from twisted.python.log import err
    from twisted.web.client import Agent, RedirectAgent
    from twisted.internet import reactor
    
    def display(response):
        print "Received response"
        print response
    
    def main():
        agent = RedirectAgent(Agent(reactor))
        d = agent.request("GET", "http://example.com/")
        d.addCallbacks(display, err)
        d.addCallback(lambda ignored: reactor.stop())
        reactor.run()
    
    if __name__ == "__main__":
        main()



    

In contrast, :api:`twisted.web.client.BrowserLikeRedirectAgent <twisted.web.client.BrowserLikeRedirectAgent>` implements
more lenient behaviour that closely emulates what web browsers do; in
other words 301 and 302 ``POST`` redirects are treated like 303,
meaning the method is changed to ``GET`` before making the redirect
request.


    



As mentioned previously, :api:`twisted.web.client.Response <Response>` contains a reference to both
the :api:`twisted.web.iweb.IClientRequest.request <request>` that it is a response
to, and the previously received :api:`twisted.web.client.Response.response <response>` , accessible by :api:`previousResponse <previousResponse>` .
In most cases there will not be a previous response, but in the case of
``RedirectAgent`` the response history can be obtained by
following the previous responses from response to response.


    



Using a HTTP proxy
~~~~~~~~~~~~~~~~~~


    

To be able to use HTTP proxies with an agent, you can use the :api:`twisted.web.client.ProxyAgent <twisted.web.client.ProxyAgent>` class.
It supports the same interface as ``Agent``, but takes the endpoint of the proxy as initializer argument.
This is specifically intended for talking to servers that implement the proxying variation of the HTTP protocol; for other types of proxies you will want :api:`twisted.web.client.Agent.usingEndpointFactory <Agent.usingEndpointFactory>` (see documentation below).

    



Here's an example demonstrating the use of an HTTP proxy running on
localhost:8000.


    



.. code-block:: python

    
    from twisted.python.log import err
    from twisted.web.client import ProxyAgent
    from twisted.internet import reactor
    from twisted.internet.endpoints import TCP4ClientEndpoint
    
    def display(response):
        print "Received response"
        print response
    
    def main():
        endpoint = TCP4ClientEndpoint(reactor, "localhost", 8000)
        agent = ProxyAgent(endpoint)
        d = agent.request("GET", "https://example.com/")
        d.addCallbacks(display, err)
        d.addCallback(lambda ignored: reactor.stop())
        reactor.run()
    
    if __name__ == "__main__":
        main()



    

Please refer to the :doc:`endpoints documentation <../../core/howto/endpoints>` for
more information about how they work and the :api:`twisted.internet.endpoints <twisted.internet.endpoints>` API documentation to learn
what other kinds of endpoints exist.


    



Handling HTTP cookies
~~~~~~~~~~~~~~~~~~~~~


    

An existing agent instance can be wrapped with
:api:`twisted.web.client.CookieAgent <twisted.web.client.CookieAgent>` to automatically
store, send and track HTTP cookies. A ``CookieJar`` 
instance, from the Python standard library module
`cookielib <http://docs.python.org/library/cookielib.html>`_ , is
used to store the cookie information. An example of using
``CookieAgent`` to perform a request and display the collected
cookies might look like this:


    



:download:`cookies.py <listings/client/cookies.py>`

.. literalinclude:: listings/client/cookies.py



Automatic Content Encoding Negotiation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


    

:api:`twisted.web.client.ContentDecoderAgent <twisted.web.client.ContentDecoderAgent>` adds
support for sending *Accept-Encoding* request headers and
interpreting *Content-Encoding* response headers.  These headers
allow the server to encode the response body somehow, typically with some
compression scheme to save on transfer
costs.  ``ContentDecoderAgent`` provides this functionality as a
wrapper around an existing agent instance.  Together with one or more
decoder objects (such as
:api:`twisted.web.client.GzipDecoder <twisted.web.client.GzipDecoder>` ), this wrapper
automatically negotiates an encoding to use and decodes the response body
accordingly.  To application code using such an agent, there is no visible
difference in the data delivered.


    



:download:`gzipdecoder.py <listings/client/gzipdecoder.py>`

.. literalinclude:: listings/client/gzipdecoder.py



Implementing support for new content encodings is as simple as writing a
new class like ``GzipDecoder`` that can decode a response using
the new encoding.  As there are not many content encodings in widespread
use, gzip is the only encoding supported by Twisted itself.


Connecting To Non-standard Destinations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Typically you want your HTTP client to open a TCP connection directly to the web server.
Sometimes however it's useful to be able to connect some other way, e.g. making an HTTP request over a SOCKS proxy connection or connecting to a server listening on a UNIX socket.
For this reason, there is an alternate constructor called :api:`twisted.web.client.Agent.usingEndpointFactory <Agent.usingEndpointFactory>` that takes an ``endpointFactory`` argument.
This argument must provide the :api:`twisted.web.iweb.IAgentEndpointFactory` interface.
Note that when talking to a HTTP proxy, i.e. a server that implements the proxying-specific variant of HTTP you should use :api:`twisted.web.client.ProxyAgent <ProxyAgent>` - see documentation above.

:download:`endpointconstructor.py <listings/client/endpointconstructor.py>`

.. literalinclude:: listings/client/endpointconstructor.py


Conclusion
----------


    

You should now understand the basics of the Twisted Web HTTP client.  In
particular, you should understand:


    




- 
  How to issue requests with arbitrary methods, headers, and bodies.
- 
  How to access the response version, code, phrase, headers, and body.
- 
  How to store, send, and track cookies.
- 
  How to control the streaming of the response body.
- 
  How to enable the HTTP persistent connection, and control the
  number of connections.
