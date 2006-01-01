import os, string, shutil

from twisted.trial import unittest, util
from twisted.python import reflect


movedModules = [('twisted.protocols.smtp', 'twisted.mail.smtp'),
                ('twisted.protocols.imap4', 'twisted.mail.imap4'),
                ('twisted.protocols.pop3', 'twisted.mail.pop3'),
                ('twisted.protocols.dns', 'twisted.names.dns'),
                ('twisted.protocols.ethernet', 'twisted.pair.ethernet'),
                ('twisted.protocols.raw', 'twisted.pair.raw'),
                ('twisted.protocols.rawudp', 'twisted.pair.rawudp'),
                ('twisted.protocols.ip', 'twisted.pair.ip'),
                ('twisted.protocols.irc', 'twisted.words.protocols.irc'),
                ('twisted.protocols.msn', 'twisted.words.protocols.msn'),
                ('twisted.protocols.toc', 'twisted.words.protocols.toc'),
                ('twisted.protocols.oscar', 'twisted.words.protocols.oscar'),
                ]


class TestCompatibility(unittest.TestCase):
    def testCompatibility(self):
        for oldName, newName in movedModules:
            try:
                old = reflect.namedModule(oldName)
                new = reflect.namedModule(newName)
            except ImportError, e:
                continue
            for someName in vars(new):
                if someName == '__doc__':
                    continue
                self.assertIdentical(getattr(old, someName),
                                     getattr(new, someName))
    testCompatibility.suppress = [util.suppress(category=DeprecationWarning)]
