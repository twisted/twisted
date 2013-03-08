# -*- test-case-name: twisted.internet.test.test_endpoints -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Fake client and server endpoint string parser plugins for testing purposes.
"""

from zope.interface.declarations import implements
from twisted.plugin import IPlugin
from twisted.internet.interfaces import (IStreamClientEndpoint,
                                         IStreamServerEndpoint,
                                         IStreamClientEndpointStringParser,
                                         IStreamServerEndpointStringParser)

class PluginBase(object):
    implements(IPlugin)

    def __init__(self, pfx):
        self.prefix = pfx



class FakeClientParser(PluginBase):

    implements(IStreamClientEndpointStringParser)

    def parseStreamClient(self, *a, **kw):
        return StreamClient(self, a, kw)



class FakeParser(PluginBase):

    implements(IStreamServerEndpointStringParser)

    def parseStreamServer(self, *a, **kw):
        return StreamServer(self, a, kw)



class EndpointBase(object):

    def __init__(self, parser, args, kwargs):
        self.parser = parser
        self.args = args
        self.kwargs = kwargs



class StreamClient(EndpointBase):

    implements(IStreamClientEndpoint)



class StreamServer(EndpointBase):

    implements(IStreamServerEndpoint)



# Instantiate plugin interface providers to register them.
fake = FakeParser('fake')
fakeClient = FakeClientParser('cfake')

