# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.trial import unittest



class DeprecationTests(unittest.TestCase):
    """
    Deprecations in L{twisted.test.proto_helpers}.
    """
    def test_AccumlatingProtocol(self):
        """
        L{proto_helpers.AccumlatingProtocol} is deprecated and
        generates a warning.
        """
        from twisted.test.proto_helpers import AccumulatingProtocol
        AccumulatingProtocol  # shush

        warnings = self.flushWarnings(
            [self.test_AccumlatingProtocol])
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(
            "twisted.test.proto_helpers.AccumulatingProtocol was "
            "deprecated in Twisted 19.3.0: Please use "
            "twisted.internet.testing.AccumulatingProtocol instead",
            warnings[0]['message'])
        self.assertEqual(1, len(warnings))


    def test_LineSendingProtocol(self):
        """
        L{proto_helpers.LineSendingProtocol} is deprecated and
        generates a warning.
        """
        from twisted.test.proto_helpers import LineSendingProtocol
        LineSendingProtocol

        warnings = self.flushWarnings(
            [self.test_LineSendingProtocol])
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(
            "twisted.test.proto_helpers.LineSendingProtocol was "
            "deprecated in Twisted 19.3.0: Please use "
            "twisted.internet.testing.LineSendingProtocol instead",
            warnings[0]['message'])
        self.assertEqual(1, len(warnings))


    def test_FakeDatagramTransport(self):
        """
        L{proto_helpers.FakeDatagramTransport} is deprecated and
        generates a warning.
        """
        from twisted.test.proto_helpers import FakeDatagramTransport
        FakeDatagramTransport

        warnings = self.flushWarnings(
            [self.test_FakeDatagramTransport])
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(
            "twisted.test.proto_helpers.FakeDatagramTransport was "
            "deprecated in Twisted 19.3.0: Please use "
            "twisted.internet.testing.FakeDatagramTransport instead",
            warnings[0]['message'])
        self.assertEqual(1, len(warnings))


    def test_StringTransport(self):
        """
        L{proto_helpers.StringTransport} is deprecated and
        generates a warning.
        """
        from twisted.test.proto_helpers import StringTransport
        StringTransport

        warnings = self.flushWarnings(
            [self.test_StringTransport])
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(
            "twisted.test.proto_helpers.StringTransport was "
            "deprecated in Twisted 19.3.0: Please use "
            "twisted.internet.testing.StringTransport instead",
            warnings[0]['message'])
        self.assertEqual(1, len(warnings))


    def test_StringTransportWithDisconnection(self):
        """
        L{proto_helpers.StringTransportWithDisconnection} is deprecated and
        generates a warning.
        """
        from twisted.test.proto_helpers import StringTransportWithDisconnection
        StringTransportWithDisconnection

        warnings = self.flushWarnings(
            [self.test_StringTransportWithDisconnection])
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(
            "twisted.test.proto_helpers.StringTransportWithDisconnection "
            "was deprecated in Twisted 19.3.0: Please use "
            "twisted.internet.testing.StringTransportWithDisconnection "
            "instead",
            warnings[0]['message'])
        self.assertEqual(1, len(warnings))


    def test_StringIOWithoutClosing(self):
        """
        L{proto_helpers.StringIOWithoutClosing} is deprecated and
        generates a warning.
        """
        from twisted.test.proto_helpers import StringIOWithoutClosing
        StringIOWithoutClosing

        warnings = self.flushWarnings(
            [self.test_StringIOWithoutClosing])
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(
            "twisted.test.proto_helpers.StringIOWithoutClosing "
            "was deprecated in Twisted 19.3.0: Please use "
            "twisted.internet.testing.StringIOWithoutClosing instead",
            warnings[0]['message'])
        self.assertEqual(1, len(warnings))


    def test_MemoryReactor(self):
        """
        L{proto_helpers.MemoryReactor} is deprecated and
        generates a warning.
        """
        from twisted.test.proto_helpers import MemoryReactor
        MemoryReactor

        warnings = self.flushWarnings(
            [self.test_MemoryReactor])
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(
            "twisted.test.proto_helpers.MemoryReactor "
            "was deprecated in Twisted 19.3.0: Please use "
            "twisted.internet.testing.MemoryReactor instead",
            warnings[0]['message'])
        self.assertEqual(1, len(warnings))


    def test_MemoryReactorClock(self):
        """
        L{proto_helpers.MemoryReactorClock} is deprecated and
        generates a warning.
        """
        from twisted.test.proto_helpers import MemoryReactorClock
        MemoryReactorClock

        warnings = self.flushWarnings(
            [self.test_MemoryReactorClock])
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(
            "twisted.test.proto_helpers.MemoryReactorClock "
            "was deprecated in Twisted 19.3.0: Please use "
            "twisted.internet.testing.MemoryReactorClock instead",
            warnings[0]['message'])
        self.assertEqual(1, len(warnings))


    def test_RaisingMemoryReactor(self):
        """
        L{proto_helpers.raisingMemoryReactor} is deprecated and
        generates a warning.
        """
        from twisted.test.proto_helpers import RaisingMemoryReactor
        RaisingMemoryReactor

        warnings = self.flushWarnings(
            [self.test_RaisingMemoryReactor])
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(
            "twisted.test.proto_helpers.RaisingMemoryReactor "
            "was deprecated in Twisted 19.3.0: Please use "
            "twisted.internet.testing.RaisingMemoryReactor instead",
            warnings[0]['message'])
        self.assertEqual(1, len(warnings))


    def test_NonStreamingProducer(self):
        """
        L{proto_helpers.NonStreamingProducer} is deprecated and
        generates a warning.
        """
        from twisted.test.proto_helpers import NonStreamingProducer
        NonStreamingProducer

        warnings = self.flushWarnings(
            [self.test_NonStreamingProducer])
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(
            "twisted.test.proto_helpers.NonStreamingProducer "
            "was deprecated in Twisted 19.3.0: Please use "
            "twisted.internet.testing.NonStreamingProducer instead",
            warnings[0]['message'])
        self.assertEqual(1, len(warnings))


    def test_waitUntilAllDisconnected(self):
        """
        L{proto_helpers.waitUntilAllDisconnected} is deprecated and
        generates a warning.
        """
        from twisted.test.proto_helpers import waitUntilAllDisconnected
        waitUntilAllDisconnected

        warnings = self.flushWarnings(
            [self.test_waitUntilAllDisconnected])
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(
            "twisted.test.proto_helpers.waitUntilAllDisconnected "
            "was deprecated in Twisted 19.3.0: Please use "
            "twisted.internet.testing.waitUntilAllDisconnected instead",
            warnings[0]['message'])
        self.assertEqual(1, len(warnings))


    def test_EventLoggingObserver(self):
        """
        L{proto_helpers.EventLoggingObserver} is deprecated and
        generates a warning.
        """
        from twisted.test.proto_helpers import EventLoggingObserver
        EventLoggingObserver

        warnings = self.flushWarnings(
            [self.test_EventLoggingObserver])
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(
            "twisted.test.proto_helpers.EventLoggingObserver "
            "was deprecated in Twisted 19.3.0: Please use "
            "twisted.internet.testing.EventLoggingObserver instead",
            warnings[0]['message'])
        self.assertEqual(1, len(warnings))
