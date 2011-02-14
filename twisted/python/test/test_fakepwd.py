# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.fakepwd}.
"""

try:
    import pwd
except ImportError:
    pwd = None


from operator import getitem

from twisted.trial.unittest import TestCase
from twisted.python.fakepwd import UserDatabase
from twisted.python.compat import set


class UserDatabaseTestsMixin:
    """
    L{UserDatabaseTestsMixin} defines tests which apply to any user database
    implementation.  Subclasses should mix it in, implement C{setUp} to create
    C{self.database} bound to a user database instance, and implement
    C{getExistingUserInfo} to return information about a user (such information
    should be unique per test method).
    """
    def test_getpwuid(self):
        """
        I{getpwuid} accepts a uid and returns the user record associated with
        it.
        """
        for i in range(2):
            # Get some user which exists in the database.
            username, password, uid, gid, gecos, dir, shell = self.getExistingUserInfo()

            # Now try to look it up and make sure the result is correct.
            entry = self.database.getpwuid(uid)
            self.assertEquals(entry.pw_name, username)
            self.assertEquals(entry.pw_passwd, password)
            self.assertEquals(entry.pw_uid, uid)
            self.assertEquals(entry.pw_gid, gid)
            self.assertEquals(entry.pw_gecos, gecos)
            self.assertEquals(entry.pw_dir, dir)
            self.assertEquals(entry.pw_shell, shell)


    def test_noSuchUID(self):
        """
        I{getpwuid} raises L{KeyError} when passed a uid which does not exist
        in the user database.
        """
        self.assertRaises(KeyError, self.database.getpwuid, -13)


    def test_getpwnam(self):
        """
        I{getpwnam} accepts a username and returns the user record associated
        with it.
        """
        for i in range(2):
            # Get some user which exists in the database.
            username, password, uid, gid, gecos, dir, shell = self.getExistingUserInfo()

            # Now try to look it up and make sure the result is correct.
            entry = self.database.getpwnam(username)
            self.assertEquals(entry.pw_name, username)
            self.assertEquals(entry.pw_passwd, password)
            self.assertEquals(entry.pw_uid, uid)
            self.assertEquals(entry.pw_gid, gid)
            self.assertEquals(entry.pw_gecos, gecos)
            self.assertEquals(entry.pw_dir, dir)
            self.assertEquals(entry.pw_shell, shell)


    def test_noSuchName(self):
        """
        I{getpwnam} raises L{KeyError} when passed a username which does not
        exist in the user database.
        """
        self.assertRaises(
            KeyError, self.database.getpwnam,
            'no' 'such' 'user' 'exists' 'the' 'name' 'is' 'too' 'long' 'and' 'has'
            '\1' 'in' 'it' 'too')


    def test_recordLength(self):
        """
        The user record returned by I{getpwuid}, I{getpwnam}, and I{getpwall}
        has a length.
        """
        db = self.database
        username, password, uid, gid, gecos, dir, shell = self.getExistingUserInfo()
        for entry in [db.getpwuid(uid), db.getpwnam(username), db.getpwall()[0]]:
            self.assertIsInstance(len(entry), int)


    def test_recordIndexable(self):
        """
        The user record returned by I{getpwuid}, I{getpwnam}, and I{getpwall}
        is indexable, with successive indexes starting from 0 corresponding to
        the values of the C{pw_name}, C{pw_passwd}, C{pw_uid}, C{pw_gid},
        C{pw_gecos}, C{pw_dir}, and C{pw_shell} attributes, respectively.
        """
        db = self.database
        username, password, uid, gid, gecos, dir, shell = self.getExistingUserInfo()
        for entry in [db.getpwuid(uid), db.getpwnam(username), db.getpwall()[0]]:
            self.assertEquals(entry[0], username)
            self.assertEquals(entry[1], password)
            self.assertEquals(entry[2], uid)
            self.assertEquals(entry[3], gid)
            self.assertEquals(entry[4], gecos)
            self.assertEquals(entry[5], dir)
            self.assertEquals(entry[6], shell)

            self.assertEquals(len(entry), len(list(entry)))
            self.assertRaises(IndexError, getitem, entry, 7)



class UserDatabaseTests(TestCase, UserDatabaseTestsMixin):
    """
    Tests for L{UserDatabase}.
    """
    def setUp(self):
        """
        Create a L{UserDatabase} with no user data in it.
        """
        self.database = UserDatabase()
        self._counter = 0


    def getExistingUserInfo(self):
        """
        Add a new user to C{self.database} and return its information.
        """
        self._counter += 1
        suffix = '_' + str(self._counter)
        username = 'username' + suffix
        password = 'password' + suffix
        uid = self._counter
        gid = self._counter + 1000
        gecos = 'gecos' + suffix
        dir = 'dir' + suffix
        shell = 'shell' + suffix

        self.database.addUser(username, password, uid, gid, gecos, dir, shell)
        return (username, password, uid, gid, gecos, dir, shell)


    def test_addUser(self):
        """
        L{UserDatabase.addUser} accepts seven arguments, one for each field of
        a L{pwd.struct_passwd}, and makes the new record available via
        L{UserDatabase.getpwuid}, L{UserDatabase.getpwnam}, and
        L{UserDatabase.getpwall}.
        """
        username = 'alice'
        password = 'secr3t'
        uid = 123
        gid = 456
        gecos = 'Alice,,,'
        home = '/users/alice'
        shell = '/usr/bin/foosh'

        db = self.database
        db.addUser(username, password, uid, gid, gecos, home, shell)

        for entry in [db.getpwuid(uid), db.getpwnam(username)]:
            self.assertEquals(entry.pw_name, username)
            self.assertEquals(entry.pw_passwd, password)
            self.assertEquals(entry.pw_uid, uid)
            self.assertEquals(entry.pw_gid, gid)
            self.assertEquals(entry.pw_gecos, gecos)
            self.assertEquals(entry.pw_dir, home)
            self.assertEquals(entry.pw_shell, shell)

        [entry] = db.getpwall()
        self.assertEquals(entry.pw_name, username)
        self.assertEquals(entry.pw_passwd, password)
        self.assertEquals(entry.pw_uid, uid)
        self.assertEquals(entry.pw_gid, gid)
        self.assertEquals(entry.pw_gecos, gecos)
        self.assertEquals(entry.pw_dir, home)
        self.assertEquals(entry.pw_shell, shell)



class PwdModuleTests(TestCase, UserDatabaseTestsMixin):
    """
    L{PwdModuleTests} runs the tests defined by L{UserDatabaseTestsMixin}
    against the built-in C{pwd} module.  This serves to verify that
    L{UserDatabase} is really a fake of that API.
    """
    if pwd is None:
        skip = "Cannot verify UserDatabase against pwd without pwd"


    def setUp(self):
        self.database = pwd
        self._users = iter(self.database.getpwall())
        self._uids = set()


    def getExistingUserInfo(self):
        """
        Read and return the next record from C{self._users}, filtering out
        any records with previously seen uid values (as these cannot be
        found with C{getpwuid} and only cause trouble).
        """
        while True:
            entry = self._users.next()
            if entry.pw_uid not in self._uids:
                self._uids.add(entry.pw_uid)
                return entry
