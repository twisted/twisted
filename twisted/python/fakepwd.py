# -*- test-case-name: twisted.python.test.test_fakepwd -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
L{twisted.python.fakepwd} provides a fake implementation of the L{pwd} API.
"""


__all__ = ['UserDatabase']


class _UserRecord(object):
    """
    L{_UserRecord} holds the user data for a single user in L{UserDatabase}.
    It corresponds to L{pwd.struct_passwd}.  See that class for attribute
    documentation.
    """
    def __init__(self, name, password, uid, gid, gecos, home, shell):
        self.pw_name = name
        self.pw_passwd = password
        self.pw_uid = uid
        self.pw_gid = gid
        self.pw_gecos = gecos
        self.pw_dir = home
        self.pw_shell = shell


    def __len__(self):
        return 7


    def __getitem__(self, index):
        return (
            self.pw_name, self.pw_passwd, self.pw_uid,
            self.pw_gid, self.pw_gecos, self.pw_dir, self.pw_shell)[index]



class UserDatabase(object):
    """
    L{UserDatabase} holds a traditional POSIX user data in memory and makes it
    available via the same API as L{pwd}.

    @ivar _users: A C{list} of L{_UserRecord} instances holding all user data
        added to this database.
    """
    def __init__(self):
        self._users = []


    def addUser(self, username, password, uid, gid, gecos, home, shell):
        """
        Add a new user record to this database.

        @param username: The value for the C{pw_name} field of the user
            record to add.
        @type username: C{str}

        @param password: The value for the C{pw_passwd} field of the user
            record to add.
        @type password: C{str}

        @param uid: The value for the C{pw_uid} field of the user record to
            add.
        @type uid: C{int}

        @param gid: The value for the C{pw_gid} field of the user record to
            add.
        @type gid: C{int}

        @param gecos: The value for the C{pw_gecos} field of the user record
            to add.
        @type gecos: C{str}

        @param home: The value for the C{pw_dir} field of the user record to
            add.
        @type home: C{str}

        @param shell: The value for the C{pw_shell} field of the user record to
            add.
        @type shell: C{str}
        """
        self._users.append(_UserRecord(
            username, password, uid, gid, gecos, home, shell))


    def getpwuid(self, uid):
        """
        Return the user record corresponding to the given uid.
        """
        for entry in self._users:
            if entry.pw_uid == uid:
                return entry
        raise KeyError()


    def getpwnam(self, name):
        """
        Return the user record corresponding to the given username.
        """
        for entry in self._users:
            if entry.pw_name == name:
                return entry
        raise KeyError()


    def getpwall(self):
        """
        Return a list of all user records.
        """
        return self._users
