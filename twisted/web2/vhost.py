##### FIXME: this file probably doesn't work.

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""I am a virtual hosts implementation.
"""

# System Imports
import string

# Sibling Imports
import resource
import responsecode
import iweb

class NameVirtualHost(resource.Resource):
    """I am a resource which represents named virtual hosts. 
       And these are my obligatory comments
    """
    
    supportNested = True

    def __init__(self, default=None):
        """Initialize. - Do you really need me to tell you that?
        """
        resource.Resource.__init__(self)
        self.hosts = {}
       
        self.default = default
        
    def addHost(self, name, resrc):
        """Add a host to this virtual host. - The Fun Stuff(TM)
            
        This associates a host named 'name' with a resource 'resrc'

            nvh.addHost('nevow.com', nevowDirectory)
            nvh.addHost('divmod.org', divmodDirectory)
            nvh.addHost('twistedmatrix.com', twistedMatrixDirectory)

        I told you that was fun.
        """
        self.hosts[name] = resrc

    def removeHost(self, name):
        """Remove a host. :(
        """
        del self.hosts[name]

    def _getResourceForRequest(self, ctx):
        """(Internal) Get the appropriate resource for the request
        """

    def locateChild(self, ctx, segments):
        """It's a NameVirtualHost, do you know where your children are?
        
        This uses locateChild magic so you don't have to mutate the request.
        """

        hostHeader = iweb.IRequest(ctx).host
        
        if hostHeader == None:
            return self.default or responsecode.NOT_FOUND
        else:
            host = hostHeader.split(':')[0].lower()
            
            if self.supportNested:
                """ If supportNested is True domain prefixes (the stuff up to the first '.')
                    will be chopped off until it's reduced to the tld or a valid domain is 
                    found.
                """

                while not self.hosts.has_key(host) and len(host.split('.')) > 1:
                    host = '.'.join(host.split('.')[1:])

        return (self.hosts.get(host, self.default) or responsecode.NOT_FOUND), segments
        

class VHostMonsterResource(resource.Resource):
    def locateChild(self, request, segments):
        if len(segments) < 2:
            return error.NoResource(), []
        else:
            if segments[0] == 'http':
                request.isSecure = lambda: 0
            elif segments[0] == 'https':
                request.isSecure = lambda: 1

            if ':' in segments[1]:
                host, port = segments[1].split(':', 1)
                port = int(port)
            else:
                host, port = segments[1], 80
           
            request.setHost(host, port)

            prefixLen = len('/'+'/'.join(request.prepath)+'/'+'/'.join(segments[:2]))
            request.path = '/'+'/'.join(segments[2:])
            request.uri = request.uri[prefixLen:]
            
            request.postpath = list(segments[2:])

            return request.site.getResourceFor(request)
