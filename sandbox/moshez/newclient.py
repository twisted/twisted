"""
Example usage:
o = opener()
o.open("http://www.yahoo.com/").addCallback(read).addCallback(util.println)
o.open("http://www.yahoo.com/").addCallback(download(sys.stdout.write))
d = o.open("http://www.yahoo.com/")
d.addCallback(download(file("yahoo.html", 'wb'))
d.addCallback(close)
"""
from twisted.internet import protocol, defer
from twisted.protocols import http
import urllib2, urlparse

class Request(urllib2.Request):

    def __init__(self, url, data=None, headers={}, visited=None):
        urllib2.Request.__init__(self, url, data, headers)
        if visited is None:
            visited = {}
        self.visited = visited


class Response:

    def __init__(self, version, status, message):
        self.version = version
        self.status = status
        self.message = message
        self.headers = {}
        self._events = []

    def handleHeader(self, key, value):
        self.headers.setdefault(key.lower(), []).append(value)

    def setHandler(self, dataReceived, connectionLost, dataDone):
        self.dataReceived = dataReceived
        self.connectionLost = connectionLost
        self.dataDone = dataDone
        for event in self._events:
            getattr(self, event[0])(*event[1:])
        del self._events

    def dataReceived(self, data):
        self._events.append(('dataReceived', data))
    def connectionLost(self, reason):
        self._events.append(('connectionLost', reason))
    def dataDone(self):
        self._events.append(('dataDone',))

class HTTPClient(http.HTTPClient):

    def connectionMade(self):
        self.factory.connection.callback(self)

    def setResponseSink(self, deferred):
        self.sink = deferred

    def handleStatus(self, version, status, message):
        self.response = Response(version, status, message)
        self.handleHeader = self.response.handleHeader

    def handleEndHeaders(self):
        self.sink.callback(self.response)
        def _(reason):
            http.HTTPClient.connectionLost(self, reason)
            if not self.done:
                self.response.connectionLost(reason)
        self.connectionLost = _

    def connectionLost(self, reason):
        http.HTTPClient.connectionLost(self, reason)
        self.sink.errback(reason)

    def handleResponsePart(self, data):
        self.response.dataReceived(data)

    def handleResponseEnd(self):
        self.done = 1
        self.response.dataDone()

class ClientFactory(protocol.ClientFactory):
    protocol = HTTPClient
    def __init__(self):
        self.connection = defer.Deferred()
    def connectionFailed(self, _, reason):
        self.connection.errback(reason)

class NoHandler(LookupError):
    pass

def sendHeaders(connection, req):
    if req.has_data():
        data = req.get_data()
        connection.sendCommand('POST', requ.get_selector())
        if not req.headers.has_key('Content-type'):
            connection.sendHeader('Content-type',
                                  'application/x-www-form-urlencoded')
        if not req.headers.has_key('Content-length'):
            connection.sendHeader('Content-length', str(len(data)))
    else:
        connection.sendCommand('GET', req.get_selector())
    connection.sendHeader('Host', req.get_host())
    for el in req.headers.iteritems():
        connection.sendHeader(*el)
    connection.endHeaders()
    if req.has_data():
        connection.transport.write(data)
    return connection

class Opener:

    def __init__(self, *handlers):
        self.handlers = list(handlers)
        for handler in self.handlers:
            handler.setOpener(self)

    def callMethod(self, name, *args, **kw):
        value = None
        for handler in self.handlers:
            value = getattr(handler, name, lambda *args,**kw:None)(*args, **kw)
            if value is not None:
                break
        if value is None:
            raise NoHandler("No handlers found for method %s" % name)
        return value

    def open(self, request, factory=None):
        try:
            self.callMethod('transform', request)
        except NoHandler:
            pass
        factory = ClientFactory()
        self.callMethod('connect_'+request.get_type(), request, factory)
        d = factory.connection
        d.addCallback(sendHeaders, request)
        def _(connection):
            d = defer.Deferred()
            connection.setResponseSink(d)
            return d
        d.addCallback(_)
        def _(response):
            try:
                response = self.callMethod('response_%s' % response.status,
                                           response, request)
            except NoHandler:
                response = self.callMethod('responseDefault', response, request)
            return response
        d.addCallback(_)
        return d

class BaseHandler:

    def setOpener(self, parent):
        self.parent = parent

HTTP_PORT = 80
HTTPS_PORT = 443

class BaseHTTPHandler(BaseHandler):

    def connect_http(self, request, factory):
        from twisted.internet import reactor
        host, port = urllib2.splitport(request.get_host())
        if port is None:
            port = HTTP_PORT
        reactor.connectTCP(host, port, factory)
        return 1 # handled

    def connect_https(self, request, factory):
        from twisted.internet import reactor
        host, port = urllib2.splitport(request.get_host())
        if port is None:
            port = HTTPS_PORT
        reactor.connectSSL(host, port, factory)
        return 1 # handled

    def responseDefault(self, response, request):
        raise response

    def response_200(self, response, request):
        return response

class HTTPRedirect(BaseHandler):

    def response_301(self, response, req):
        h = response.headers
        url = (h.get('location') or h.get('uri') or [None])[0]
        if url is None:
            raise response
        url = urlparse.urljoin(req.get_full_url(), url)
        if len(req.visited)>10 or url in req.visited:
            raise ValueError("redirection loop detected", url)
        return self.parent.open(Request(url, req.get_data(),
                                        req.headers, req.visited))

    response_307 = response_302 = response_301

    def response_303(self, response, req):
        req.add_data(None)
        return response_302(self, response, req)


class ProxyHandler(BaseHandler):

    def __init__(self, proxies=None):
        if proxies is None:
            proxies = urllib2.getproxies()
        self.proxies = proxies

    def connect_http(self, request, factory):
        origType = request.get_type()
        proxy = self.proxies.get(origType)
        if not proxy:
            return
        type, url = urllib2.splittype(proxy)
        host, _ = urllib2.splithost(url)
        if '@' in host:
            user, host = host.split('@', 1)
            user = base64.encodestring(unquote(user_pass)).strip()
            request.add_header('Proxy-Authorization', 'Basic '+user)
        host = unquote(host)
        request.set_proxy(host, type)
        if origType == type:
            return
        else:
            return self.callMethod('connect_'+request.type, request, factory)

    connect_https = connect_http

def opener():
    return Opener(ProxyHandler(), BaseHTTPHandler(), HTTPRedirect())

def read(response):
    d, l = defer.Deferred(), []
    response.setHandler(
        dataReceived=l.append,
        dataDone=lambda:d.callback(''.join(l)),
        connectionLost=d.errback,
    )
    return d

def download(fp):
    def _(response):
        d = defer.Deferred()
        response.setHandler(
            dataReceived=fp.write,
            dataDone=lambda:d.callback(fp),
            connectionLost=d.errback,
        )
        return d
    return _

def close(fp):
    fp.close()

def urlopen(url, data=None):
    return opener().open(Request(url, data))

def urlretrieve(name, url, data=None):
    d = opener().open(Request(url, data))
    d.addCallback(download(file(name, 'wb')))
    d.addCallback(close)
    return d

if __name__ == '__main__':
    from twisted.internet import reactor
    import sys
    opener().open(Request('http://www.yahoo.com/')
    ).addCallback(download(sys.stdout))
    reactor.run()
