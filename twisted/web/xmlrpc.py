
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
import xmlrpclib, sys, traceback

# Sibling Imports
from twisted.web import resource


class NoSuchFunction(Exception):
    """There is no function by the given name."""
    pass


class XMLRPC(resource.Resource):
    """A resource that implements XML-RPC.
    
    You probably want to connect this to '/RPC2'.
    """
    
    isLeaf = 1
    
    def render(self, request):
        args, functionPath = xmlrpclib.loads(request.content)
        try:
            function = self._getFunction(functionPath)
        except NoSuchFunction:
            result = xmlrpclib.Fault(1, "no such function")
        else:
            try:
                result = (apply(function, args), )
            except:
                traceback.print_exc(file=sys.stdout)
                result = xmlrpclib.Fault(2, "error")
        
        request.setHeader("content-type", "text/xml")
        return xmlrpclib.dumps(result, methodresponse=1)
    
    def _getFunction(self, functionPath):
        """Given a string, return a function, or raise NoSuchFunction.
        
        Override in subclasses.
        """
        raise NotImplementedError, "implement in subclass"


class PB(XMLRPC):
    """Publish a pb.Perspective instance using XML-RPC."""
    
    def __init__(self, perspective):
        XMLRPC.__init__(self)
        self.perspective = perspective
    
    def _getFunction(self, functionPath):
        """Convert the functionPath to a method beginning with 'perspective_'.
        
        For example, 'echo' returns the method 'perspective_echo'
        of self.perspective.
        """
        f = getattr(self.perspective, "perspective_%s" % functionPath, None)
        if f:
            return f
        else:
            raise NoSuchFunction
