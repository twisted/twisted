
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

from twisted.names import dns
from twisted.internet import main

def printMessage( message ):
    print "ID:", message.id
    print "IsAnswer:", message.answer
    print "rCode:", message.rCode
    print "Queries:"
    for q in message.queries:
        print q.name.name
    for list, title in ( ( message.answers, "Answers:" ),
                         ( message.ns, "NS:" ),
                         ( message.add, "Additional records:" ) ):
        print title
        for rr in list:
            print rr.name,
            for i in range( len( rr.data ) ):
                print ord( rr.data[ i ] ),
            print


class X:
    def __init__( self ):
        self.n = 0
        self.boss = dns.DNSBoss()

    def handleAnswer( self, message ):
        printMessage( message )
        self.n = self.n + 1
        print "N =", self.n
        if self.n == 2:
            self.boss.stopReadingBoth()
            main.shutDown()

x = X()

x.boss.queryUDP( ( "129.199.129.1", 53 ),
                 "clipper.ens.fr",
                 x.handleAnswer )

x.boss.queryTCP( ( "129.199.129.1", 53 ),
                 "clipper.ens.fr",
                 x.handleAnswer )

main.run()
