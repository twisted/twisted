# Copyright (c) 2001 actzero, inc. All rights reserved.

import socket, sys
sys.path.insert(1, '..')
import lettucewrap
socket.socket = lettucewrap.GreenSocket

def main():
    from SOAPpy import SOAPProxy

    ident = '$Id: cardClient.py,v 1.3 2003/05/09 12:46:11 warnes Exp $'

    endpoint = "http://localhost:12027/xmethodsInterop"
    sa = "urn:soapinterop"
    ns = "http://soapinterop.org/"

    serv = SOAPProxy(endpoint, namespace=ns, soapaction=sa)
    try: hand =  serv.dealHand(NumberOfCards = 13, StringSeparator = '\n')
    except: print "no dealHand"; hand = 0
    try: sortedhand = serv.dealArrangedHand(NumberOfCards=13,StringSeparator='\n')
    except: print "no sorted"; sortedhand = 0
    try: card = serv.dealCard()
    except: print "no card"; card = 0

    print "*****hand****\n",hand,"\n*********"
    print "******sortedhand*****\n",sortedhand,"\n*********"
    print "card:",card

from twisted.internet import reactor
from twisted.python import log

#log.startLogging(sys.stdout)

reactor.callLater(0, lettucewrap.wrapCall, main)
reactor.run()

