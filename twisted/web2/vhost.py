##### FIXME: this file probably doesn't work.

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""I am a virtual hosts implementation.
"""

# System Imports
import string

# Twisted Imports
from twisted.python import roots

# Sibling Imports
import resource
import error

from nevow import rend
from nevow import loaders
from nevow.stan import directive
from nevow.tags import *
from nevow import inevow

class VirtualHostList(rend.Page):
    def __init__(self, nvh):
        rend.Page.__init__(self)
        self.nvh = nvh

    stylesheet = """
    body { border: 0; padding: 0; margin: 0; background-color: #efefef; }
    h1 {padding: 0.1em; background-color: #777; color: white; border-bottom: thin white dashed;}
"""

    def getStyleSheet(self):
        return self.stylesheet
 
    def data_hostlist(self, context, data):
        return self.nvh.hosts.keys()

    def render_hostlist(self, context, data):
        host=data
        req = context.locate(inevow.IRequest)
        proto = req.clientproto.split('/')[0].lower()

        link = "%s://%s" % (proto, host)

        if ':' in req.getHeader('host'):
            port = req.getHeader('host').split(':')[1]
            
            if port != 80:
                link += ":%s" % port

        link += req.path

        return context.tag[a(href=link)[ host ]]
 
    def render_title(self, context, data):
        req = context.locate(inevow.IRequest)
        proto = req.clientproto.split('/')[0].lower()
        host = req.getHeader('host')
        return context.tag[ "Virtual Host Listing for %s://%s" % (proto, host) ]

    docFactory = loaders.stan(
        html[
            head[
                title(render=render_title),
                style(type="text/css")[
                    getStyleSheet
                ]
            ],
            body[
                h1(render=render_title),
                ul(data=directive("hostlist"), render=directive("sequence"))[
                    li(pattern="item", render=render_hostlist)]]])

class NameVirtualHost(resource.Resource):
    """I am a resource which represents named virtual hosts. 
       And these are my obligatory comments
    """
    
    supportNested = True

    def __init__(self, default=None, listHosts=True):
        """Initialize. - Do you really need me to tell you that?
        """
        resource.Resource.__init__(self)
        self.hosts = {}
       
        self.default = default
        self.listHosts = listHosts
        
        if self.listHosts and self.default == None:
            self.default = VirtualHostList(self)
            
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

    def _getResourceForRequest(self, request):
        """(Internal) Get the appropriate resource for the request
        """
        
        hostHeader = request.getHeader('host')
        
        if hostHeader == None:
            return self.default or error.NoResource()
        else:
            host = hostHeader.split(':')[0].lower()
            
            if self.supportNested:
                """ If supportNested is True domain prefixes (the stuff up to the first '.')
                    will be chopped off until it's reduced to the tld or a valid domain is 
                    found.
                """

                while not self.hosts.has_key(host) and len(host.split('.')) > 1:
                    host = '.'.join(host.split('.')[1:])

        return (self.hosts.get(host, self.default) or error.NoResource())

    def locateChild(self, request, segments):
        """It's a NameVirtualHost, do you know where your children are?
        
        This uses locateChild magic so you don't have to mutate the request.
        """
        resrc = self._getResourceForRequest(request)
        return resrc, segments
        

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
