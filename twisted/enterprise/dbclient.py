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

from twisted.internet import tcp, main
from twisted.spread import pb
import time
import sys

class clientCollector(pb.Referenced):

    def __init__(self, player):
        self.player = player
        self.count = 0
        self.start = time.time()        

    def remote_gotData(self, *data):
        #print "Got some data:" , self.count
        self.player.request("select * from accounts", self)
        self.count = self.count + 1
        if self.count == 400:
            now = time.time()
            print "Started at %f finished at %f took %f" % ( self.start, now, now - self.start)
            main.shutDown()

class DbClient:

    def __init__(self, host, name, password):
        self.host = host
        self.name = name
        self.password = password
        self.player = None
        self.count = 0


    def doLogin(self):
        self.client = pb.Broker()
        tcp.Client(self.host, 8787, self.client)

        self.client.requestIdentity("twisted",  # username
                                    "matrix",  # password
                                    callback = self.preConnected,
                                    errback  = self.couldntConnect)

    def couldntConnect(self, arg):
        print "Could not connect.", arg

    def preConnected(self, identity):
        print "preConnected."
        identity.attach("twisted.enterprise.db","twisted",  None, pbcallback=self.gotConnection, pberrback=self.couldntConnect)

    def gotConnection(self, player):
        print 'connected:', player
        self.player = player
        self.collector = clientCollector(player)
        self.player.request("select * from accounts", self.collector)



def run():
    c = DbClient("localhost", "twisted", "matrix")
    c.doLogin()
    main.run()


if __name__ == '__main__':
    run()


