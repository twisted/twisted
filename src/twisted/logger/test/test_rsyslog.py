# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.logger.rsyslog}.
"""

from twisted.internet import protocol
from twisted.logger import Logger, LogPublisher
from twisted.logger.rsyslog import RemoteSyslogObserver
from twisted.trial.unittest import TestCase
from twisted.internet.test.reactormixins import ReactorBuilder


class RsyslogReceiver(protocol.DatagramProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.received = []

    def datagramReceived(self, data, addr):
        self.received.append(data)


class RemoteSyslogTests(TestCase):
    """
    Tests for L{RemoteSyslogObserver}.
    """

    def setUp(self):
        reactor = self.buildReactor()
        self.rx = RsyslogReceiver()
        self.p = reactor.listenUDP(0, self.rx, interface="127.0.0.1")
        self.port = self.p.getHost().port

    def tearDown(self):
        return self.p.stopListening()

    def test_capture(self) -> None:
        """
        Events logged are forwarded to an rsyslog server.
        """
        obs = LogPublisher()
        self.log = Logger("rsyslog", observer=obs)
        obs.addObserver(RemoteSyslogObserver("127.0.0.1", port=self.port))

        self.log.debug("Capture this, please")
        self.log.info("Capture this too, please")

        self.assertTrue(len(self.rx.received) == 2)
        self.assertEqual(self.rx.received[0], b"")
        self.assertEqual(self.rx.received[1], b"")

globals().update(ReactorBuilder.makeTestCaseClasses())
