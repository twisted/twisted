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

"""Coil plugin for web support."""

from twisted.web import static, server, resource, vhost, test, proxy
from twisted.coil import app, coil

import types


# site configuration

class SiteConfigurator(app.ProtocolFactoryConfigurator):
    """Configurator for web sites."""
    
    configurableClass = server.Site
    configTypes = {'resource': resource.Resource}
    configName = 'HTTP Web Site'

def siteFactory(container, name):
    d = static.Data(
        """
        <html><head><title>Blank Page</title></head>
        <body>
        <h1>This Page Left Intentionally Blank</h1>
        </body>
        </html>""",
        "text/html")
    d.isLeaf = 1
    return server.Site(d)

coil.registerConfigurator(SiteConfigurator, siteFactory)


# resource configuration

class ResourceConfigurator(coil.Configurator):
    """Base class for web resource configurators."""
    
    configurableClass = resource.Resource

coil.registerConfigurator(ResourceConfigurator, None)


class StaticConfigurator(ResourceConfigurator):
    
    configurableClass = static.File
    
    configTypes = {'path': types.StringType,
                   'execCGI': 'boolean',
                   'execEPY': 'boolean',
                   'defaultType': types.StringType}

    configName = 'Web Filesystem Access'

    def config_execCGI(self, allowed):
        instance = self.instance
        if allowed:
            from twisted.web import twcgi
            instance.processors['.cgi'] = twcgi.CGIScript
        else:
            if instance.processors.has_key('.cgi'):
                del instance.processors['.cgi']

    def config_execEPY(self, allowed):
        instance = self.instance
        if allowed:
            from twisted.web import script
            instance.processors['.epy'] = script.PythonScript
        else:
            if instance.processors.has_key('.epy'):
                del instance.processors['.epy']

    def getConfiguration(self):
        instance = self.instance
        return {'path': instance.path,
                'execCGI': instance.processors.has_key('.cgi'),
                'execEPY': instance.processors.has_key('.epy'),
                'defaultType': instance.defaultType}

def staticFactory(container, name):
    return static.File("somewhere/outthere")

coil.registerConfigurator(StaticConfigurator, staticFactory)


class TestConfigurator(ResourceConfigurator):

    configurableClass = test.Test
    configName = "Web Test Widget"

def testFactory(container, name):
    return test.Test()

coil.registerConfigurator(TestConfigurator, testFactory)


class VirtualHostConfigurator(ResourceConfigurator):
    
    configurableClass = vhost.NameVirtualHost
    configName = "Virtual Host Resource"

def vhostFactory(container, name):
    return vhost.NameVirtualHost()

coil.registerConfigurator(VirtualHostConfigurator, vhostFactory)


class ReverseProxyConfigurator(ResourceConfigurator):

    configurableClass = proxy.ReverseProxyResource
    configName = "HTTP Reverse Proxy"
    
    configTypes = {'path': types.StringType,
                   'host': types.StringType,
                   'port': types.IntType}

def proxyFactory(container, name):
    return proxy.ReverseProxyResource("www.yahoo.com", 80, "/")

coil.registerConfigurator(ReverseProxyConfigurator, proxyFactory)
