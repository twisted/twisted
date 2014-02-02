#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An example demonstrating how to send and receive UDP broadcast messages.

Every second, this application will send out a PING message with a unique ID.
It will respond to all PING messages with a PONG (including ones sent by
itself). You can tell how many copies of this script are running on the local
network by the number of "RECV PONG".

Run using twistd:

$ twistd -ny udpbroadcast.py
"""

from uuid import uuid4

from twisted.application import internet, service
from twisted.internet.protocol import DatagramProtocol
from twisted.python import log



class PingPongProtocol(DatagramProtocol):
    noisy = False

    def __init__(self, controller, port):
        self.port = port


    def startProtocol(self):
        self.transport.setBroadcastAllowed(True)


    def sendPing(self):
        pingMsg = "PING {0}".format(uuid4().hex)
        self.transport.write(pingMsg, ('<broadcast>', self.port))
        log.msg("SEND " + pingMsg)


    def datagramReceived(self, datagram, addr):
        if datagram[:4] == "PING":
            uuid = datagram[5:]
            pongMsg = "PONG {0}".format(uuid)
            self.transport.write(pongMsg, ('<broadcast>', self.port))
            log.msg("RECV " + datagram)
        elif datagram[:4] == "PONG":
            log.msg("RECV " + datagram)



class Broadcaster(object):

    def ping(self, proto):
        proto.sendPing()


    def makeService(self):
        application = service.Application('Broadcaster')

        root = service.MultiService()
        root.setServiceParent(application)

        proto = PingPongProtocol(controller=self, port=8555)
        root.addService(internet.UDPServer(8555, proto))
        root.addService(internet.TimerService(1, self.ping, proto))

        return application


application = Broadcaster().makeService()
