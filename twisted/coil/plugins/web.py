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
from twisted.coil import coil
from twisted.python import components

import types


# site configuration

class SiteConfigurator(coil.Configurator):
    """Configurator for web sites."""
    
    __implements__ = [coil.IConfigurator, coil.IStaticCollection]
    
    configurableClass = server.Site
    configTypes = {'resource': [resource.IResource, "Resource", "The resource at the site's root."] }
    configName = 'HTTP Web Site'
    
    def listStaticEntities(self):
        return [['resource', self.instance.resource]]

    def getStaticEntity(self, name):
        if name == 'resource':
            return self.instance.resource

components.registerAdapter(SiteConfigurator, server.Site, coil.ICollection)

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

class MimeTypeCollection(coil.ConfigCollection):

    entityType = types.StringType


class StaticConfigurator(coil.Configurator, coil.StaticCollection):
    
    __implements__ = [coil.IConfigurator, coil.IStaticCollection]
    
    configurableClass = static.File
    
    configTypes = {'path': [types.StringType, "Path", "The path in the filesystem to be served."],
                   'execCGI': ['boolean', "Execute CGIs", "Support running CGI scripts."],
                   'execEPY': ['boolean', "Execute EPYs", "Support running EPY scripts."],
                   'defaultType': [types.StringType, "Default MIME Type", "MIME type for files whose type can't be guessed."],
                   'allowExt': [types.IntType, "Allow extensions to be ignored (0 or 1)", "Specify wether or not requests for /foo will return /foo.ext if it exists."]
                  }

    configName = 'Web Filesystem Access'

    def __init__(self, instance):
        coil.Configurator.__init__(self, instance)
        coil.StaticCollection.__init__(self)
        self.putEntity("Mime-types", MimeTypeCollection(self.instance.contentTypes))
        self.putEntity("Resources", coil.CollectionWrapper(self.instance))
        self.lock()
    
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
                'defaultType': instance.defaultType,
                'allowExt': instance.allowExt}

def staticFactory(container, name):
    return static.File("somewhere/outthere")

coil.registerConfigurator(StaticConfigurator, staticFactory)
components.registerAdapter(StaticConfigurator, static.File, coil.ICollection)

class TestConfigurator(coil.Configurator):

    configurableClass = test.Test
    configName = "Web Test Widget"

def testFactory(container, name):
    return test.Test()

coil.registerConfigurator(TestConfigurator, testFactory)


class VirtualHostConfigurator(coil.Configurator):
    
    configurableClass = vhost.NameVirtualHost
    configName = "Virtual Host Resource"

def vhostFactory(container, name):
    return vhost.NameVirtualHost()

coil.registerConfigurator(VirtualHostConfigurator, vhostFactory)


class ReverseProxyConfigurator(coil.Configurator):

    configurableClass = proxy.ReverseProxyResource
    configName = "HTTP Reverse Proxy"
    
    configTypes = {'path': [types.StringType, "Remote Path", "The path on the remote server, e.g. '/foo'."],
                   'host': [types.StringType, "Remote Host", "The remote host, e.g. 'www.yahoo.com'"],
                   'port': [types.IntType, "Remote Port", "The remote port, typically 80."]}

def proxyFactory(container, name):
    return proxy.ReverseProxyResource("www.yahoo.com", 80, "/")

coil.registerConfigurator(ReverseProxyConfigurator, proxyFactory)
