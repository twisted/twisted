# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.test.iosim}.
"""

from __future__ import absolute_import, division

from zope.interface import implementer

from twisted.internet.interfaces import IPushProducer
from twisted.internet.protocol import Protocol

from twisted.test.iosim import FakeTransport, connect
from twisted.trial.unittest import TestCase


class FakeTransportTests(TestCase):
    """
    Tests for L{FakeTransport}.
    """

    def test_connectionSerial(self):
        """
        Each L{FakeTransport} receives a serial number that uniquely identifies
        it.
        """
        a = FakeTransport(object(), True)
        b = FakeTransport(object(), False)
        self.assertIsInstance(a.serial, int)
        self.assertIsInstance(b.serial, int)
        self.assertNotEqual(a.serial, b.serial)


    def test_writeSequence(self):
        """
        L{FakeTransport.writeSequence} will write a sequence of L{bytes} to the
        transport.
        """
        a = FakeTransport(object(), False)

        a.write(b"a")
        a.writeSequence([b"b", b"c", b"d"])

        self.assertEqual(b"".join(a.stream), b"abcd")



@implementer(IPushProducer)
class StrictPushProducer(object):
    """
    A L{IPushProducer} implementation which produces nothing but enforces
    preconditions on its state transition methods.
    """
    _state = u"running"

    def stopProducing(self):
        if self._state == u"stopped":
            raise ValueError(u"Cannot stop already-stopped IPushProducer")
        self._state = u"stopped"


    def pauseProducing(self):
        if self._state != u"running":
            raise ValueError(
                u"Cannot pause {} IPushProducer".format(self._state)
            )
        self._state = u"paused"


    def resumeProducing(self):
        if self._state != u"paused":
            raise ValueError(
                u"Cannot resume {} IPushProducer".format(self._state)
            )
        self._state = u"running"



class IOPumpTests(TestCase):
    """
    Tests for L{IOPump}.
    """
    def _testStreamingProducer(self, mode):
        """
        Connect a couple protocol/transport pairs to an L{IOPump} and then pump
        it.  Verify that a streaming producer registered with one of the
        transports does not receive invalid L{IPushProducer} method calls and
        ends in the right state.
        """
        serverProto = Protocol()
        serverTransport = FakeTransport(serverProto, isServer=False)

        clientProto = Protocol()
        clientTransport = FakeTransport(clientProto, isServer=False)

        pump = connect(
            serverProto, serverTransport,
            clientProto, clientTransport,
            greet=False,
        )

        producer = StrictPushProducer()
        victim = {
            u"server": serverTransport,
            u"client": clientTransport,
        }[mode]
        victim.registerProducer(producer, streaming=True)

        pump.pump()
        self.assertEqual(u"running", producer._state)


    def test_serverStreamingProducer(self):
        """
        L{IOPump.pump} does not call C{resumeProducing} on a L{IPushProducer}
        (stream producer) registered with the server transport.
        """
        self._testStreamingProducer(mode=u"server")


    def test_clientStreamingProducer(self):
        """
        L{IOPump.pump} does not call C{resumeProducing} on a L{IPushProducer}
        (stream producer) registered with the client transport.
        """
        self._testStreamingProducer(mode=u"client")
