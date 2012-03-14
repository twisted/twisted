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
                                         IStreamServerEndpointStringParser,
                                         IListeningPort)
from twisted.internet import defer

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

    listener = None

    def listen(self, *a, **kw):
        self.listener = ListeningPort(a, kw)
        return defer.succeed(self.listener)



class ListeningPort(object):

    implements(IListeningPort)

    def __init__(self, args, kwargs):
        self.args = args
        self.kwargs = kwargs
        self.listening = False
        self.host = object()


    def startListening(self):
        self.listening = True


    def stopListening(self):
        self.listening = False
        return defer.succeed(None)


    def getHost(self):
        return self.host



class FakeClientParserWithReactor(PluginBase):

    implements(IStreamClientEndpointStringParser)

    def parseStreamClient(self, reactor, **kw):
        return StreamClient(self, reactor, kw)



class FakeClientParserWithoutReactor(PluginBase):

    implements(IStreamClientEndpointStringParser)

    def parseStreamClient(self, **kw):
        return StreamClient(self, None, kw)



class FailingFakeClientParser(PluginBase):

    implements(IStreamClientEndpointStringParser)

    def parseStreamClient(self):
        raise TypeError()



# Instantiate plugin interface providers to register them.
fake = FakeParser('fake')
fakeClient = FakeClientParser('cfake')
fakeClientWithReactor = FakeClientParserWithReactor('crfake')
fakeClientWithoutReactor = FakeClientParserWithoutReactor('c-rfake')
failingFakeClient = FailingFakeClientParser('fcfake')
