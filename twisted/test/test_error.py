# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.trial import unittest
from twisted.internet import error
import socket

class TestStringification(unittest.TestCase):
    """Test that the exceptions have useful stringifications.
    """

    listOfTests = [
        #(output, exception[, args[, kwargs]]),

        ("An error occurred binding to an interface.",
         error.BindError),

        ("An error occurred binding to an interface: foo.",
         error.BindError, ['foo']),

        ("An error occurred binding to an interface: foo bar.",
         error.BindError, ['foo', 'bar']),

        ("Couldn't listen on eth0:4242: Foo.",
         error.CannotListenError,
         ('eth0', 4242, socket.error('Foo'))),

        ("Message is too long to send.",
         error.MessageLengthError),

        ("Message is too long to send: foo bar.",
         error.MessageLengthError, ['foo', 'bar']),

        ("DNS lookup failed.",
         error.DNSLookupError),

        ("DNS lookup failed: foo bar.",
         error.DNSLookupError, ['foo', 'bar']),

        ("An error occurred while connecting.",
         error.ConnectError),

        ("An error occurred while connecting: someOsError.",
         error.ConnectError, ['someOsError']),

        ("An error occurred while connecting: foo.",
         error.ConnectError, [], {'string': 'foo'}),

        ("An error occurred while connecting: someOsError: foo.",
         error.ConnectError, ['someOsError', 'foo']),

        ("Couldn't bind.",
         error.ConnectBindError),

        ("Couldn't bind: someOsError.",
         error.ConnectBindError, ['someOsError']),

        ("Couldn't bind: someOsError: foo.",
         error.ConnectBindError, ['someOsError', 'foo']),

        ("Hostname couldn't be looked up.",
         error.UnknownHostError),

        ("No route to host.",
         error.NoRouteError),

        ("Connection was refused by other side.",
         error.ConnectionRefusedError),

        ("TCP connection timed out.",
         error.TCPTimedOutError),

        ("File used for UNIX socket is no good.",
         error.BadFileError),

        ("Service name given as port is unknown.",
         error.ServiceNameUnknownError),

        ("User aborted connection.",
         error.UserError),

        ("User timeout caused connection failure.",
         error.TimeoutError),

        ("An SSL error occurred.",
         error.SSLError),

        ("Connection to the other side was lost in a non-clean fashion.",
         error.ConnectionLost),

        ("Connection to the other side was lost in a non-clean fashion: foo bar.",
         error.ConnectionLost, ['foo', 'bar']),

        ("Connection was closed cleanly.",
         error.ConnectionDone),

        ("Connection was closed cleanly: foo bar.",
         error.ConnectionDone, ['foo', 'bar']),

        ("Uh.", #TODO nice docstring, you've got there.
         error.ConnectionFdescWentAway),

        ("Tried to cancel an already-called event.",
         error.AlreadyCalled),

        ("Tried to cancel an already-called event: foo bar.",
         error.AlreadyCalled, ['foo', 'bar']),

        ("Tried to cancel an already-cancelled event.",
         error.AlreadyCancelled),

        ("A process has ended without apparent errors: process finished with exit code 0.",
         error.ProcessDone,
         [None]),

        ("A process has ended with a probable error condition: process ended.",
         error.ProcessTerminated),

        ("A process has ended with a probable error condition: process ended with exit code 42.",
         error.ProcessTerminated,
         [],
         {'exitCode': 42}),

        ("A process has ended with a probable error condition: process ended by signal SIGBUS.",
         error.ProcessTerminated,
         [],
         {'signal': 'SIGBUS'}),

        ("The Connector was not connecting when it was asked to stop connecting.",
         error.NotConnectingError),

        ("The Port was not listening when it was asked to stop listening.",
         error.NotListeningError),

        ]

    def testThemAll(self):
        for entry in self.listOfTests:
            output = entry[0]
            exception = entry[1]
            try:
                args = entry[2]
            except IndexError:
                args = ()
            try:
                kwargs = entry[3]
            except IndexError:
                kwargs = {}

            self.assertEqual(
                str(exception(*args, **kwargs)),
                output)


    def test_connectionLostSubclassOfConnectionClosed(self):
        """
        L{error.ConnectionClosed} is a superclass of L{error.ConnectionLost}.
        """
        self.assertTrue(issubclass(error.ConnectionLost,
                                   error.ConnectionClosed))


    def test_connectionDoneSubclassOfConnectionClosed(self):
        """
        L{error.ConnectionClosed} is a superclass of L{error.ConnectionDone}.
        """
        self.assertTrue(issubclass(error.ConnectionDone,
                                   error.ConnectionClosed))

