#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This is a sample implementation of a Twisted push producer/consumer system. It
consists of a TCP server which asks the user how many random integers they
want, and it sends the result set back to the user, one result per line,
and finally closes the connection.
"""

from __future__ import print_function

from sys import stdout
from random import randrange

from zope.interface import implementer
from twisted.python.log import startLogging
from twisted.internet import interfaces, reactor
from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver


@implementer(interfaces.IPushProducer)
class Producer(object):
    """
    Send back the requested number of random integers to the client.
    """

    def __init__(self, proto, count):
        self._proto = proto
        self._goal = count
        self._produced = 0
        self._paused = False

    def pauseProducing(self):
        """
        When we've produced data too fast, pauseProducing() will be called
        (reentrantly from within resumeProducing's sendLine() method, most
        likely), so set a flag that causes production to pause temporarily.
        """
        self._paused = True
        print('Pausing connection from %s' % self._proto.transport.getPeer())

    def resumeProducing(self):
        """
        Resume producing integers.

        This tells the push producer to (re-)add itself to the main loop and
        produce integers for its consumer until the requested number of integers
        were returned to the client.
        """
        self._paused = False

        while not self._paused and self._produced < self._goal:
            next_int = randrange(0, 10000)
            self._proto.sendLine('%d' % next_int)
            self._produced += 1

        if self._produced == self._goal:
            self._proto.transport.unregisterProducer()
            self._proto.transport.loseConnection()

    def stopProducing(self):
        """
        When a consumer has died, stop producing data for good.
        """
        self._produced = self._goal


class ServeRandom(LineReceiver):
    """
    Serve up random integers.
    """

    def connectionMade(self):
        """
        Once the connection is made we ask the client how many random integers
        the producer should return.
        """
        print('Connection made from %s' % self.transport.getPeer())
        self.sendLine('How many random integers do you want?')

    def lineReceived(self, line):
        """
        This checks how many random integers the client expects in return and
        tells the producer to start generating the data.
        """
        count = int(line.strip())
        print('Client requested %d random integers!' % count)
        producer = Producer(self, count)
        self.transport.registerProducer(producer, True)
        producer.resumeProducing()

    def connectionLost(self, reason):
        print('Connection lost from %s' % self.transport.getPeer())


startLogging(stdout)
factory = Factory()
factory.protocol = ServeRandom
reactor.listenTCP(1234, factory)
reactor.run()
