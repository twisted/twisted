# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests L{twisted.conch.unix}
"""

unix = None
try:
    from twisted.conch import unix
except:
    skip = "can't run on non-posix computers"

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


    def test_requestAvatarPassesNonAnonymousNames(self):
        """
        If the avatarId passed to C{requestAvatar} is not
        L{twisted.cred.checkers.ANONYMOUS}, the avatarId is returned as is
        """
        realm = unix.UnixSSHRealm()
        ignore1, user, ignore2 = realm.requestAvatar('notAnonymous', None,
                                                     (None,))
        self.assertEqual(user.username, 'notAnonymous')


    def test_requestAvatarChecksForAnonymousAccess(self):
        """
        The anonymous avatar gets passed to C{requestAvatar} for any realm.
        L{unix.UnixSSHRealm} doesn't know how to handle this yet, so it raises
        C{NotImplementedError}
        """
        realm = unix.UnixSSHRealm()
        self.assertRaises(NotImplementedError, realm.requestAvatar,
                          ANONYMOUS, None, (None,))
