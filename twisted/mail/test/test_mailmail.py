# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.mail.scripts.mailmail}, the implementation of the
command line program I{mailmail}.
"""

import sys
from StringIO import StringIO

from twisted.trial.unittest import TestCase
from twisted.mail.scripts.mailmail import parseOptions


class OptionsTests(TestCase):
    """
    Tests for L{parseOptions} which parses command line arguments and reads
    message text from stdin to produce an L{Options} instance which can be
    used to send a message.
    """
    def test_unspecifiedRecipients(self):
        """
        If no recipients are given in the argument list and there is no
        recipient header in the message text, L{parseOptions} raises
        L{SystemExit} with a string describing the problem.
        """
        self.addCleanup(setattr, sys, 'stdin', sys.stdin)
        sys.stdin = StringIO(
            'Subject: foo\n'
            '\n'
            'Hello, goodbye.\n')
        exc = self.assertRaises(SystemExit, parseOptions, [])
        self.assertEqual(exc.args, ('No recipients specified.',))


    def test_listQueueInformation(self):
        """
        The I{-bp} option for listing queue information is unsupported and
        if it is passed to L{parseOptions}, L{SystemExit} is raised.
        """
        exc = self.assertRaises(SystemExit, parseOptions, ['-bp'])
        self.assertEqual(exc.args, ("Unsupported option.",))


    def test_stdioTransport(self):
        """
        The I{-bs} option for using stdin and stdout as the SMTP transport
        is unsupported and if it is passed to L{parseOptions}, L{SystemExit}
        is raised.
        """
        exc = self.assertRaises(SystemExit, parseOptions, ['-bs'])
        self.assertEqual(exc.args, ("Unsupported option.",))


    def test_ignoreFullStop(self):
        """
        The I{-i} and I{-oi} options for ignoring C{"."} by itself on a line
        are unsupported and if either is passed to L{parseOptions},
        L{SystemExit} is raised.
        """
        exc = self.assertRaises(SystemExit, parseOptions, ['-i'])
        self.assertEqual(exc.args, ("Unsupported option.",))
        exc = self.assertRaises(SystemExit, parseOptions, ['-oi'])
        self.assertEqual(exc.args, ("Unsupported option.",))


    def test_copyAliasedSender(self):
        """
        The I{-om} option for copying the sender if they appear in an alias
        expansion is unsupported and if it is passed to L{parseOptions},
        L{SystemExit} is raised.
        """
        exc = self.assertRaises(SystemExit, parseOptions, ['-om'])
        self.assertEqual(exc.args, ("Unsupported option.",))
