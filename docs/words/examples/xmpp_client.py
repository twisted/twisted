#!/usr/bin/python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A very simple twisted xmpp-client (Jabber ID)

To run the script:
$ python xmpp_client.py <jid> <secret>
"""

from __future__ import print_function

import sys

from twisted.internet.defer import Deferred
from twisted.internet.task import react
from twisted.names.srvconnect import SRVConnector
from twisted.words.xish import domish
from twisted.words.protocols.jabber import xmlstream, client
from twisted.words.protocols.jabber.jid import JID


class Client(object):
    def __init__(self, reactor, jid, secret):
        self.reactor = reactor
        f = client.XMPPClientFactory(jid, secret)
        f.addBootstrap(xmlstream.STREAM_CONNECTED_EVENT, self.connected)
        f.addBootstrap(xmlstream.STREAM_END_EVENT, self.disconnected)
        f.addBootstrap(xmlstream.STREAM_AUTHD_EVENT, self.authenticated)
        f.addBootstrap(xmlstream.INIT_FAILED_EVENT, self.init_failed)
        connector = SRVConnector(
            reactor, 'xmpp-client', jid.host, f, defaultPort=5222)
        connector.connect()
        self.finished = Deferred()


    def rawDataIn(self, buf):
        print("RECV: %r" % buf)


    def rawDataOut(self, buf):
        print("SEND: %r" % buf)


    def connected(self, xs):
        print('Connected.')

        self.xmlstream = xs

        # Log all traffic
        xs.rawDataInFn = self.rawDataIn
        xs.rawDataOutFn = self.rawDataOut


    def disconnected(self, xs):
        print('Disconnected.')

        self.finished.callback(None)


    def authenticated(self, xs):
        print("Authenticated.")

        presence = domish.Element((None, 'presence'))
        xs.send(presence)

        self.reactor.callLater(5, xs.sendFooter)


    def init_failed(self, failure):
        print("Initialization failed.")
        print(failure)

        self.xmlstream.sendFooter()



def main(reactor, jid, secret):
    """
    Connect to the given Jabber ID and return a L{Deferred} which will be
    called back when the connection is over.

    @param reactor: The reactor to use for the connection.
    @param jid: A L{JID} to connect to.
    @param secret: A C{str}
    """
    return Client(reactor, JID(jid), secret).finished


if __name__ == '__main__':
    react(main, sys.argv[1:])
