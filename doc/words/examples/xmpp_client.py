# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import sys
from twisted.internet import reactor
from twisted.names.srvconnect import SRVConnector
from twisted.words.xish import domish
from twisted.words.protocols.jabber import xmlstream, client, jid


class XMPPClientConnector(SRVConnector):
    def __init__(self, reactor, domain, factory):
        SRVConnector.__init__(self, reactor, 'xmpp-client', domain, factory)


    def pickServer(self):
        host, port = SRVConnector.pickServer(self)

        if not self.servers and not self.orderedServers:
            # no SRV record, fall back..
            port = 5222

        return host, port



class Client(object):
    def __init__(self, client_jid, secret):
        f = client.XMPPClientFactory(client_jid, secret)
        f.addBootstrap(xmlstream.STREAM_CONNECTED_EVENT, self.connected)
        f.addBootstrap(xmlstream.STREAM_END_EVENT, self.disconnected)
        f.addBootstrap(xmlstream.STREAM_AUTHD_EVENT, self.authenticated)
        f.addBootstrap(xmlstream.INIT_FAILED_EVENT, self.init_failed)
        connector = XMPPClientConnector(reactor, client_jid.host, f)
        connector.connect()


    def rawDataIn(self, buf):
        print "RECV: %s" % unicode(buf, 'utf-8').encode('ascii', 'replace')


    def rawDataOut(self, buf):
        print "SEND: %s" % unicode(buf, 'utf-8').encode('ascii', 'replace')


    def connected(self, xs):
        print 'Connected.'

        self.xmlstream = xs

        # Log all traffic
        xs.rawDataInFn = self.rawDataIn
        xs.rawDataOutFn = self.rawDataOut


    def disconnected(self, xs):
        print 'Disconnected.'

        reactor.stop()


    def authenticated(self, xs):
        print "Authenticated."

        presence = domish.Element((None, 'presence'))
        xs.send(presence)

        reactor.callLater(5, xs.sendFooter)


    def init_failed(self, failure):
        print "Initialization failed."
        print failure

        self.xmlstream.sendFooter()


client_jid = jid.JID(sys.argv[1])
secret = sys.argv[2]
c = Client(client_jid, secret)

reactor.run()
