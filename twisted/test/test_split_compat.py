import os, string, shutil

from twisted.trial import unittest
from twisted.python import reflect


movedModules = [('twisted.protocols.smtp', 'twisted.mail.smtp'),
                ('twisted.protocols.imap4', 'twisted.mail.imap4'),
                ('twisted.protocols.pop3', 'twisted.mail.pop3'),
                ('twisted.protocols.dns', 'twisted.names.dns')]


class TestCompatibility(unittest.TestCase):
    def testCompatibility(self):
        self.expectedAssertions = len(movedModules)
        for oldName, newName in movedModules:
            try:
                old = reflect.namedModule(oldName)
                new = reflect.namedModule(newName)
            except ImportError, e:
                self.expectedAssertions -= 1
                continue
            someName = vars(old).keys()[0]
            self.assertIdentical(getattr(old, someName),
                                 getattr(new, someName))
            
