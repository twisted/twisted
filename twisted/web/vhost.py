"""I am a virtual hosts implementation."""

# System Imports
import string

# Sibling Imports
import resource
import error

class NameVirtualHost(resource.Resource):
    """I am a resource which represents named virtual hosts.
    """

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
        host = string.lower(request.getHeader('host'))
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
