
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""A generic resource for publishing objects via XML-RPC.

Requires xmlrpclib (comes standard with Python 2.2 and later, otherwise can be
downloaded from http://www.pythonware.com/products/xmlrpc/).
"""

# System Imports
import xmlrpclib

# Sibling Imports
from twisted.web import resource, server
from twisted.internet import defer
from twisted.python import log


# Error codes for Twisted, if they conflict with yours then
# modify them at runtime.
NOT_FOUND = 8001
FAILURE = 8002


# Useful so people don't need to import xmlrpclib directly
Fault = xmlrpclib.Fault


class NoSuchFunction(Exception):
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
    Deferreds, or Handler instances.

    By default methods beginning with 'xmlrpc_' are published.
    """
    
    isLeaf = 1
    
    def __init__(self):
        resource.Resource.__init__(self)
        self.requests = {}
    
    def requestFinished(self, request):
        del self.requests[request]
    
    def render(self, request):
        request.content.seek(0, 0)
        args, functionPath = xmlrpclib.loads(request.content.read())
        try:
            function = self._getFunction(functionPath)
        except NoSuchFunction:
            result = Fault(NOT_FOUND, "no such function %s" % functionPath)
        else:
            try:
                result = apply(function, args)
            except:
                log.deferr()
                result = Fault(FAILURE, "error")
        
        request.setHeader("content-type", "text/xml")
        if isinstance(result, Handler):
            result = result.result
        if isinstance(result, defer.Deferred):
            responder = _DeferredResult(self, request)
            self.requests[responder] = 1
            result.addCallbacks(responder.gotResult, responder.gotFailure)
            return server.NOT_DONE_YET
        else:
            if not isinstance(result, Fault):
                result = (result,) # wrap as tuple
            return xmlrpclib.dumps(result, methodresponse=1)
    
    def _getFunction(self, functionPath):
        """Given a string, return a function, or raise NoSuchFunction.
        
        This returned function will be called, and should return the result
        of the call, a Deferred, or a Fault instance.
        
        Override in subclasses if you want your own policy. The default
        policy is that given functionPath 'foo', return the method at
        self.xmlrpc_foo, i.e. getattr(self, "xmlrpc_" + functionPath).
        """
        f = getattr(self, "xmlrpc_%s" % functionPath, None)
        if f and callable(f):
            return f
        else:
            raise NoSuchFunction


class _DeferredResult:
    """The deferred result of an XML-RPC request."""
    
    def __init__(self, resource, request):
        self.resource = resource
        self.request = request
    
    def gotResult(self, result):
        """Callback for when request finished."""
        if not isinstance(result, Fault):
            result = (result,)
        self.finish(result)

    def gotFailure(self, error):
        """Callback for when request failed."""
        self.finish(Fault(FAILURE, "error"))

    def finish(self, result):
        self.request.write(xmlrpclib.dumps(result, methodresponse=1))
        self.request.finish()
        self.resource.requestFinished(self)
        del self.resource


__all__ = ["XMLRPC", "Handler", "NoSuchFunction", "Fault"]
