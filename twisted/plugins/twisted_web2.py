# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from zope.interface import implements

from twisted.plugin import IPlugin
from twisted.web2.iweb import IResource

class _Web2ResourcePlugin(object):
    implements(IPlugin, IResource)

    def __init__(self, name, className, description):
        self.name = name
        self.className = className
        self.description = description

TestResource = _Web2ResourcePlugin("TestResource",
                           "twisted.web2.plugin.TestResource",
                           "I'm a test resource")


from twisted.application.service import ServiceMaker

TwistedWeb2 = ServiceMaker('Twisted Web2',
                         'twisted.web2.tap',
                         ("An HTTP/1.1 web server that can serve from a "
                          "filesystem or application resource."),
                         "web2")
