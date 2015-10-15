# Copyright (c) Twisted Matrix Laboratories
# See LICENSE for details

"""
A PTY server that spawns a shell upon connection.

Run this example by typing in:
> python ptyserv.py

Telnet to the server once you start it by typing in: 
> telnet localhost 5823
"""

from twisted.internet import reactor, protocol

class FakeTelnet(protocol.Protocol):
    commandToRun = ['/bin/sh'] # could have args too
    dirToRunIn = '/tmp'
    def connectionMade(self):
        print 'connection made'
        self.propro = ProcessProtocol(self)
        reactor.spawnProcess(self.propro, self.commandToRun[0], self.commandToRun, {},
                             self.dirToRunIn, usePTY=1)
    def dataReceived(self, data):
        self.propro.transport.write(data)
    def conectionLost(self, reason):
        print 'connection lost'
        self.propro.tranport.loseConnection()

class ProcessProtocol(protocol.ProcessProtocol):

    def __init__(self, pr):
        self.pr = pr

    def outReceived(self, data):
        self.pr.transport.write(data)
    
    def processEnded(self, reason):
        print 'protocol connection lost'
        self.pr.transport.loseConnection()

f = protocol.Factory()
f.protocol = FakeTelnet
reactor.listenTCP(5823, f)
reactor.run()
