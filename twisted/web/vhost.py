
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

"""I am a virtual hosts implementation."""

# System Imports
import string

# Sibling Imports
import resource
import error

class NameVirtualHost(resource.Resource):
    """I am a resource which represents named virtual hosts.
    """

    default = None

    def __init__(self):
        """Initialize.
        """
        resource.Resource.__init__(self)
        self.hosts = {}

    def addHost(self, name, resrc):
        """Add a host to this virtual host.

        This will take a host named `name', and map it to a resource
        `resrc'.  For example, a setup for our virtual hosts would be::

            nvh.addHost('divunal.com', divunalDirectory)
            nvh.addHost('www.divunal.com', divunalDirectory)
            nvh.addHost('twistedmatrix.com', twistedMatrixDirectory)
            nvh.addHost('www.twistedmatrix.com', twistedMatrixDirectory)
        """
        self.hosts[name] = resrc

    def _getResourceForRequest(self, request):
        """(Internal) Get the appropriate resource for the given host.
        """
        hostHeader = request.getHeader('host')
        if hostHeader == None:
            return self.default or error.NoResource()
        else:
            host = string.split(string.lower(hostHeader),':')[0]
        return self.hosts.get(host, error.NoResource("host %s not in vhost map" % repr(host)))

    def render(self, request):
        """Implementation of resource.Resource's render method.
        """
        resrc = self._getResourceForRequest(request)
        return resrc.render(request)

    def getChild(self, path, request):
        """Implementation of resource.Resource's getChild method.
        """
        resrc = self._getResourceForRequest(request)
        return resrc.getChildWithDefault(path, request)
