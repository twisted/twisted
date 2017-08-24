# -*- test-case-name: twisted.mail.test.test_mailmail -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.mail.scripts.mailmail}, the implementation of the
command line program I{mailmail}.
"""

import os
import sys

from twisted.copyright import version
from twisted.mail import smtp
from twisted.mail.scripts import mailmail
from twisted.mail.scripts.mailmail import parseOptions
from twisted.python.compat import NativeStringIO
from twisted.python.runtime import platformType
from twisted.test.proto_helpers import MemoryReactor
from twisted.trial.unittest import TestCase


class OptionsTests(TestCase):
    """
    Tests for L{parseOptions} which parses command line arguments and reads
    message text from stdin to produce an L{Options} instance which can be
    used to send a message.
    """
    out = NativeStringIO()
    memoryReactor = MemoryReactor()

    def setUp(self):
        """
        Override some things in mailmail, so that we capture C{stdout},
        and do not call L{reactor.stop}.
        """
        # Override the mailmail logger, so we capture stderr output
        from twisted.logger import textFileLogObserver, Logger
        logObserver = textFileLogObserver(self.out)
        self.patch(mailmail, '_log', Logger(observer=logObserver))

        # Override mailmail.sendmail, so we don't call reactor.stop()
        def sendmail(host, options, ident):
            smtp.sendmail(host, options.sender, options.to, options.body,
                          reactor=self.memoryReactor)

        self.patch(mailmail, 'sendmail', sendmail)


    def test_unspecifiedRecipients(self):
        """
        If no recipients are given in the argument list and there is no
        recipient header in the message text, L{parseOptions} raises
        L{SystemExit} with a string describing the problem.
        """
        self.patch(sys, 'stdin', NativeStringIO(
            'Subject: foo\n'
            '\n'
            'Hello, goodbye.\n'))
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


    def test_version(self):
        """
        The I{--version} option displays the version and raises
        L{SystemExit}.
        """
        out = NativeStringIO()
        self.patch(sys, 'stdout', out)
        systemExitCode = self.assertRaises(SystemExit, parseOptions, '--version')
        # SystemExit.code is None on success
        self.assertEqual(systemExitCode.code, None)
        data = out.getvalue()
        self.assertEqual(data, "mailmail version: {}\n".format(version))


    def test_backGroundDelivery(self):
        """
        The I{-odb} flag specifies background delivery.
        """
        stdin = NativeStringIO('\n')
        self.patch(sys, 'stdin', stdin)
        o = parseOptions("-odb")
        self.assertTrue(o.background)


    def test_foreGroundDelivery(self):
        """
        The I{-odf} flags specifies foreground delivery.
        """
        stdin = NativeStringIO('\n')
        self.patch(sys, 'stdin', stdin)
        o = parseOptions("-odf")
        self.assertFalse(o.background)


    def test_recipientsFromHeaders(self):
        """
        The I{-t} flags specifies that recipients should be obtained
        from headers.
        """
        stdin = NativeStringIO(
            'To: Curly <invaliduser2@example.com>\n'
            'Cc: Larry <invaliduser1@example.com>\n'
            'Bcc: Moe <invaliduser3@example.com>\n'
            '\n'
            'Oh, a wise guy?\n')
        self.patch(sys, 'stdin', stdin)
        o = parseOptions("-t")
        self.assertEqual(len(o.to), 3)


    def test_setFrom(self):
        """
        The I{-F} flags specifies the From: value.
        """
        self.patch(sys, 'stderr', self.out)
        stdin = NativeStringIO(
            'To: invaliduser2@example.com\n'
            'Subject: A wise guy?\n\n')
        self.patch(sys, 'stdin', stdin)
        o = parseOptions(["-F", "Larry <invaliduser1@example.com>", "-t"])
        self.assertEqual(o.sender, "Larry <invaliduser1@example.com>")
        # Test that -F flag is overridden by From: value in header
        sys.stdin = NativeStringIO(
            'To: Curly <invaliduser4@example.com>\n'
            'From: Shemp <invaliduser4@example.com>\n')
        o = parseOptions(["-F", "Groucho <invaliduser5@example.com>", "-t"])
        self.assertEqual(o.sender, "invaliduser4@example.com")


    def test_run(self):
        """
        L{twisted.mail.scripts.mailmail.run}
        """
        self.addCleanup(setattr, sys, 'argv', sys.argv)
        self.addCleanup(setattr, sys, 'stdin', sys.stdin)
        self.patch(sys, 'stderr', self.out)
        sys.argv = ("test_mailmail.py", "invaliduser2@example.com", "-oep")
        sys.stdin = NativeStringIO('\n')
        mailmail.run()

    if platformType == "win32":
        test_run.skip = "win32 lacks support for getuid()"


    def test_readConfig(self):
        """
        Reading the configuration from a file.
        """
        self.addCleanup(setattr, sys, 'argv', sys.argv)

        filename = self.mktemp()
        myUid = os.getuid()
        myGid = os.getgid()

        with open(filename, "w") as f:
            # Create a config file with some invalid values
            f.write("[useraccess]\n"
                    "allow=invaliduser2,invaliduser1\n"
                    "deny=invaliduser3,invaliduser4,{}\n"
                    "order=allow,deny\n"
                    "[groupaccess]\n"
                    "allow=invalidgid1,invalidgid2\n"
                    "deny=invalidgid1,invalidgid2,{}\n"
                    "order=deny,allow\n"
                    "[identity]\n"
                    "localhost=funny\n"
                    "[addresses]\n"
                    "smarthost=localhost\n"
                    "default_domain=example.com\n".format(myUid, myGid))

        # Override LOCAL_CFG with the file we just created
        self.patch(mailmail, "LOCAL_CFG", filename)
        stdin = NativeStringIO('\n')
        self.patch(sys, 'stdin', stdin)

        argv = ("test_mailmail.py", "invaliduser2@example.com", "-oep")
        self.patch(sys, 'argv', argv)
        mailmail.run()
        self.assertRegex(self.out.getvalue(),
                         "Illegal UID in \[useraccess\] section: invaliduser1")
        self.assertRegex(self.out.getvalue(),
                         "Illegal GID in \[groupaccess\] section: invalidgid1")
        self.assertRegex(self.out.getvalue(),
                         'Illegal entry in \[identity\] section: funny')

    if platformType == "win32":
        test_readConfig.skip = "win32 lacks support for getuid()"
