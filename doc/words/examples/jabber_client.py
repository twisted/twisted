# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# Originally written by Darryl Vandorp
# http://randomthoughts.vandorp.ca/

from twisted.words.protocols.jabber import client, jid
from twisted.words.xish import domish
from twisted.internet import reactor
        
def authd(xmlstream):
    print "authenticated"

    presence = domish.Element(('jabber:client','presence'))
    xmlstream.send(presence)
    
    xmlstream.addObserver('/message',  debug)
    xmlstream.addObserver('/presence', debug)
    xmlstream.addObserver('/iq',       debug)   

def debug(elem):
    print elem.toXml().encode('utf-8')
    print "="*20
    
myJid = jid.JID('username@server.jabber/twisted_words')
factory = client.basicClientFactory(myJid, 'password')
factory.addBootstrap('//event/stream/authd',authd)
reactor.connectTCP('server.jabber',5222,factory)
reactor.run()
