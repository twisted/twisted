# -*- test-case-name: twisted.web.test.test_xmlrpc -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""A generic resource for publishing objects via XML-RPC.

Requires xmlrpclib (comes standard with Python 2.2 and later, otherwise can be
downloaded from http://www.pythonware.com/products/xmlrpc/).

API Stability: semi-stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""
from __future__ import nested_scopes

__version__ = "$Revision: 1.32 $"[11:-2]

# System Imports
import xmlrpclib
import urlparse

# Sibling Imports
from twisted.web import resource, server
from twisted.internet import defer, protocol, reactor
from twisted.python import log, reflect
from twisted.web import http

# These are deprecated, use the class level definitions
NOT_FOUND = 8001
FAILURE = 8002


# Useful so people don't need to import xmlrpclib directly
Fault = xmlrpclib.Fault
Binary = xmlrpclib.Binary
Boolean = xmlrpclib.Boolean
DateTime = xmlrpclib.DateTime


class NoSuchFunction(Fault):
    """There is no function by the given name."""
    pass


class Handler:
    """Handle a XML-RPC request and store the state for a request in progress.

    Override the run() method and return result using self.result,
    a Deferred.

    We require this class since we're not using threads, so we can't
    encapsulate state in a running function if we're going  to have
    to wait for results.

    For example, lets say we want to authenticate against twisted.cred,
    run a LDAP query and then pass its result to a database query, all
    as a result of a single XML-RPC command. We'd use a Handler instance
    to store the state of the running command.
    """

    def __init__(self, resource, *args):
        self.resource = resource # the XML-RPC resource we are connected to
        self.result = defer.Deferred()
        self.run(*args)
    
    def run(self, *args):
        # event driven equivalent of 'raise UnimplementedError'
        self.result.errback(NotImplementedError("Implement run() in subclasses"))


class XMLRPC(resource.Resource):
    """A resource that implements XML-RPC.
    
    You probably want to connect this to '/RPC2'.

    Methods published can return XML-RPC serializable results, Faults,
    Binary, Boolean, DateTime, Deferreds, or Handler instances.

    By default methods beginning with 'xmlrpc_' are published.

    Sub-handlers for prefixed methods (e.g., system.listMethods)
    can be added with putSubHandler. By default, prefixes are
    separated with a '.'. Override self.separator to change this.
    """

    # Error codes for Twisted, if they conflict with yours then
    # modify them at runtime.
    NOT_FOUND = 8001
    FAILURE = 8002

    isLeaf = 1
    separator = '.'

    def __init__(self):
        resource.Resource.__init__(self)
        self.subHandlers = {}

    def putSubHandler(self, prefix, handler):
        self.subHandlers[prefix] = handler

    def getSubHandler(self, prefix):
        return self.subHandlers.get(prefix, None)

    def getSubHandlerPrefixes(self):
        return self.subHandlers.keys()

    def render(self, request):
        request.content.seek(0, 0)
        args, functionPath = xmlrpclib.loads(request.content.read())
        try:
            function = self._getFunction(functionPath)
        except Fault, f:
            self._cbRender(f, request)
        else:
            request.setHeader("content-type", "text/xml")
            defer.maybeDeferred(function, *args).addErrback(
                self._ebRender
            ).addCallback(
                self._cbRender, request
            )
        return server.NOT_DONE_YET

    def _cbRender(self, result, request):
        if isinstance(result, Handler):
            result = result.result
        if not isinstance(result, Fault):
            result = (result,)
        try:
            s = xmlrpclib.dumps(result, methodresponse=1)
        except:
            f = Fault(self.FAILURE, "can't serialize output")
            s = xmlrpclib.dumps(f, methodresponse=1)
        request.setHeader("content-length", str(len(s)))
        request.write(s)
        request.finish()

    def _ebRender(self, failure):
        if isinstance(failure.value, Fault):
            return failure.value
        log.err(failure)
        return Fault(self.FAILURE, "error")

    def _getFunction(self, functionPath):
        """Given a string, return a function, or raise NoSuchFunction.

        This returned function will be called, and should return the result
        of the call, a Deferred, or a Fault instance.

        Override in subclasses if you want your own policy. The default
        policy is that given functionPath 'foo', return the method at
        self.xmlrpc_foo, i.e. getattr(self, "xmlrpc_" + functionPath).
        If functionPath contains self.separator, the sub-handler for
        the initial prefix is used to search for the remaining path.
        """
        if functionPath.find(self.separator) != -1:
            prefix, functionPath = functionPath.split(self.separator, 1)
            handler = self.getSubHandler(prefix)
            if handler is None: raise NoSuchFunction(self.NOT_FOUND, "no such subHandler %s" % prefix)
            return handler._getFunction(functionPath)

        f = getattr(self, "xmlrpc_%s" % functionPath, None)
        if not f:
            raise NoSuchFunction(self.NOT_FOUND, "function %s not found" % functionPath)
        elif not callable(f):
            raise NoSuchFunction(self.NOT_FOUND, "function %s not callable" % functionPath)
        else:
            return f

    def _listFunctions(self):
        """Return a list of the names of all xmlrpc methods."""
        return reflect.prefixedMethodNames(self.__class__, 'xmlrpc_')


class XMLRPCIntrospection(XMLRPC):
    """Implement the XML-RPC Introspection API.

    By default, the methodHelp method returns the 'help' method attribute,
    if it exists, otherwise the __doc__ method attribute, if it exists,
    otherwise the empty string.

    To enable the methodSignature method, add a 'signature' method attribute
    containing a list of lists. See methodSignature's documentation for the
    format. Note the type strings should be XML-RPC types, not Python types.
    """

    def __init__(self, parent):
        """Implement Introspection support for an XMLRPC server.

        @param parent: the XMLRPC server to add Introspection support to.
        """

        XMLRPC.__init__(self)
        self._xmlrpc_parent = parent

    def xmlrpc_listMethods(self):
        """Return a list of the method names implemented by this server."""
        functions = []
        todo = [(self._xmlrpc_parent, '')]
        while todo:
            obj, prefix = todo.pop(0)
            functions.extend([ prefix + name for name in obj._listFunctions() ])
            todo.extend([ (obj.getSubHandler(name),
                           prefix + name + obj.separator)
                          for name in obj.getSubHandlerPrefixes() ])
        return functions

    xmlrpc_listMethods.signature = [['array']]

    def xmlrpc_methodHelp(self, method):
        """Return a documentation string describing the use of the given method.
        """
        method = self._xmlrpc_parent._getFunction(method)
        return (getattr(method, 'help', None)
                or getattr(method, '__doc__', None) or '')

    xmlrpc_methodHelp.signature = [['string', 'string']]

    def xmlrpc_methodSignature(self, method):
        """Return a list of type signatures.

        Each type signature is a list of the form [rtype, type1, type2, ...]
        where rtype is the return type and typeN is the type of the Nth
        argument. If no signature information is available, the empty
        string is returned.
        """
        method = self._xmlrpc_parent._getFunction(method)
        return getattr(method, 'signature', None) or ''

    xmlrpc_methodSignature.signature = [['array', 'string'],
                                        ['string', 'string']]


def addIntrospection(xmlrpc):
    """Add Introspection support to an XMLRPC server.

    @param xmlrpc: The xmlrpc server to add Introspection support to.
    """
    xmlrpc.putSubHandler('system', XMLRPCIntrospection(xmlrpc))


class QueryProtocol(http.HTTPClient):

    def connectionMade(self):
        self.sendCommand('POST', self.factory.url)
        self.sendHeader('User-Agent', 'Twisted/XMLRPClib')
        self.sendHeader('Host', self.factory.host)
        self.sendHeader('Content-type', 'text/xml')
        self.sendHeader('Content-length', str(len(self.factory.payload)))
        self.endHeaders()
        self.transport.write(self.factory.payload)

    def handleStatus(self, version, status, message):
        if status != '200':
            self.factory.badStatus(status, message)

    def handleResponse(self, contents):
        self.factory.parseResponse(contents)


payloadTemplate = """<?xml version="1.0"?>
<methodCall>
<methodName>%s</methodName>
%s
</methodCall>
"""


class QueryFactory(protocol.ClientFactory):

    deferred = None
    protocol = QueryProtocol

    def __init__(self, url, host, method, *args):
        self.url, self.host = url, host
        self.payload = payloadTemplate % (method, xmlrpclib.dumps(args))
        self.deferred = defer.Deferred()

    def parseResponse(self, contents):
        if not self.deferred:
            return
        try:
            response = xmlrpclib.loads(contents)
        except xmlrpclib.Fault, error:
            self.deferred.errback(error)
            self.deferred = None
        else:
            self.deferred.callback(response[0][0])
            self.deferred = None

    def clientConnectionLost(self, _, reason):
        if self.deferred is not None:
            self.deferred.errback(reason)
            self.deferred = None

    clientConnectionFailed = clientConnectionLost

    def badStatus(self, status, message):
        self.deferred.errback(ValueError(status, message))
        self.deferred = None


class Proxy:
    """A Proxy for making remote XML-RPC calls.

    Pass the URL of the remote XML-RPC server to the constructor.

    Use proxy.callRemote('foobar', *args) to call remote method
    'foobar' with *args.
    """

    def __init__(self, url):
        parts = urlparse.urlparse(url)
        self.url = urlparse.urlunparse(('', '')+parts[2:])
        if self.url == "":
            self.url = "/"
        if ':' in parts[1]:
            self.host, self.port = parts[1].split(':')
            self.port = int(self.port)
        else:
            self.host, self.port = parts[1], None
        self.secure = parts[0] == 'https'

    def callRemote(self, method, *args):
        factory = QueryFactory(self.url, self.host, method, *args)
        if self.secure:
            from twisted.internet import ssl
            reactor.connectSSL(self.host, self.port or 443,
                               factory, ssl.ClientContextFactory())
        else:
            reactor.connectTCP(self.host, self.port or 80, factory)
        return factory.deferred

__all__ = ["XMLRPC", "Handler", "NoSuchFunction", "Fault", "Proxy"]
