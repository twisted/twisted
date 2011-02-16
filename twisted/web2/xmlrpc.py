# -*- test-case-name: twisted.web2.test.test_xmlrpc -*-
#
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
A generic resource for publishing objects via XML-RPC.

Maintainer: Itamar Shtull-Trauring
"""

# System Imports
import xmlrpclib

# Sibling Imports
from twisted.web2 import resource, stream
from twisted.web2 import responsecode, http, http_headers
from twisted.internet import defer
from twisted.python import log, reflect

# Useful so people don't need to import xmlrpclib directly
Fault = xmlrpclib.Fault
Binary = xmlrpclib.Binary
Boolean = xmlrpclib.Boolean
DateTime = xmlrpclib.DateTime


class NoSuchFunction(Fault):
    """There is no function by the given name."""
    pass


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
        # For GET/HEAD: Return an error message
        s=("<html><head><title>XML-RPC responder</title></head>"
           "<body><h1>XML-RPC responder</h1>POST your XML-RPC here.</body></html>")
        
        return http.Response(responsecode.OK,
            {'content-type': http_headers.MimeType('text', 'html')},
            s)
    
    def http_POST(self, request):
        parser, unmarshaller = xmlrpclib.getparser()
        deferred = stream.readStream(request.stream, parser.feed)
        deferred.addCallback(lambda x: self._cbDispatch(
            request, parser, unmarshaller))
        deferred.addErrback(self._ebRender)
        deferred.addCallback(self._cbRender, request)
        return deferred

    def _cbDispatch(self, request, parser, unmarshaller):
        parser.close()
        args, functionPath = unmarshaller.close(), unmarshaller.getmethodname()

        function = self.getFunction(functionPath)
        return defer.maybeDeferred(function, request, *args)

    def _cbRender(self, result, request):
        if not isinstance(result, Fault):
            result = (result,)
        try:
            s = xmlrpclib.dumps(result, methodresponse=1)
        except:
            f = Fault(self.FAILURE, "can't serialize output")
            s = xmlrpclib.dumps(f, methodresponse=1)
        return http.Response(responsecode.OK,
            {'content-type': http_headers.MimeType('text', 'xml')},
            s)

    def _ebRender(self, failure):
        if isinstance(failure.value, Fault):
            return failure.value
        log.err(failure)
        return Fault(self.FAILURE, "error")

    def getFunction(self, functionPath):
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
            if handler is None:
                raise NoSuchFunction(self.NOT_FOUND, "no such subHandler %s" % prefix)
            return handler.getFunction(functionPath)

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

    def xmlrpc_listMethods(self, request):
        """Return a list of the method names implemented by this server."""
        functions = []
        todo = [(self._xmlrpc_parent, '')]
        while todo:
            obj, prefix = todo.pop(0)
            functions.extend([prefix + name for name in obj._listFunctions()])
            todo.extend([(obj.getSubHandler(name),
                           prefix + name + obj.separator)
                          for name in obj.getSubHandlerPrefixes()])
        functions.sort()
        return functions

    xmlrpc_listMethods.signature = [['array']]

    def xmlrpc_methodHelp(self, request, method):
        """Return a documentation string describing the use of the given method.
        """
        method = self._xmlrpc_parent.getFunction(method)
        return (getattr(method, 'help', None)
                or getattr(method, '__doc__', None) or '')

    xmlrpc_methodHelp.signature = [['string', 'string']]

    def xmlrpc_methodSignature(self, request, method):
        """Return a list of type signatures.

        Each type signature is a list of the form [rtype, type1, type2, ...]
        where rtype is the return type and typeN is the type of the Nth
        argument. If no signature information is available, the empty
        string is returned.
        """
        method = self._xmlrpc_parent.getFunction(method)
        return getattr(method, 'signature', None) or ''

    xmlrpc_methodSignature.signature = [['array', 'string'],
                                        ['string', 'string']]


def addIntrospection(xmlrpc):
    """Add Introspection support to an XMLRPC server.

    @param xmlrpc: The xmlrpc server to add Introspection support to.
    """
    xmlrpc.putSubHandler('system', XMLRPCIntrospection(xmlrpc))


__all__ = ["XMLRPC", "NoSuchFunction", "Fault"]
