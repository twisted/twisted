# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests L{twisted.conch.unix}
"""

import pwd

from twisted.conch import unix
from twisted.cred.checkers import ANONYMOUS
from twisted.trial.unittest import TestCase



class FakeUnixConchUser(object):
    def __init__(self, username):
        self.username = username
        self.logout = None



class UnixSSHRealmTestCase(TestCase):
    """
    Tests for L{twisted.conch.unix.UnixSSHRealm}
    """
    def setUp(self):
        self.patch(unix, 'UnixConchUser', FakeUnixConchUser)


    def testRequestAvatarPassesNonAnonymousNames(self):
        realm = unix.UnixSSHRealm()
        ignore1, user, ignore2 = realm.requestAvatar('notAnonymous', None,
                                                     (None,))
        self.assertEqual(user.username, 'notAnonymous')


    def testRequestAvatarChecksForAnonymousAccess(self):
        fake_passwdb = pwd.struct_passwd(
            ('running_username', '*', 1, 1, 'x', '/temp', '/bin/zsh'))

        self.patch(unix.pwd, 'getpwuid', lambda *args, **kwargs: fake_passwdb)
        self.patch(unix.os, 'getuid', lambda: 1)
        realm = unix.UnixSSHRealm()
        ignore1, user, ignore2 = realm.requestAvatar(ANONYMOUS, None, (None,))
        self.assertEqual(user.username, 'running_username')
