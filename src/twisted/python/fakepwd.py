# -*- test-case-name: twisted.python.test.test_fakepwd -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
L{twisted.python.fakepwd} provides a fake implementation of the L{pwd} API.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from pwd import struct_passwd
else:
    from collections import namedtuple

    struct_passwd = namedtuple(
        "struct_passwd",
        ["pw_name", "pw_passwd", "pw_uid", "pw_gid", "pw_gecos", "pw_dir", "pw_shell"],
    )._make
__all__ = ["UserDatabase", "ShadowDatabase"]


class UserDatabase:
    """
    L{UserDatabase} holds a traditional POSIX user data in memory and makes it
    available via the same API as L{pwd}.

    @ivar _users: A C{list} of L{struct_passwd} instances holding all user data
        added to this database.
    """

    _users: list[struct_passwd]

    def __init__(self) -> None:
        self._users = []

    def addUser(
        self,
        username: str,
        password: str,
        uid: int,
        gid: int,
        gecos: str,
        home: str,
        shell: str,
    ) -> None:
        """
        Add a new user record to this database.

        @param username: The value for the C{pw_name} field of the user
            record to add.

        @param password: The value for the C{pw_passwd} field of the user
            record to add.

        @param uid: The value for the C{pw_uid} field of the user record to
            add.

        @param gid: The value for the C{pw_gid} field of the user record to
            add.

        @param gecos: The value for the C{pw_gecos} field of the user record
            to add.

        @param home: The value for the C{pw_dir} field of the user record to
            add.

        @param shell: The value for the C{pw_shell} field of the user record to
            add.
        """
        self._users.append(
            struct_passwd((username, password, uid, gid, gecos, home, shell))
        )

    def getpwuid(self, uid: int) -> struct_passwd:
        """
        Return the user record corresponding to the given uid.
        """
        for entry in self._users:
            if entry.pw_uid == uid:
                return entry
        raise KeyError()

    def getpwnam(self, name: str) -> struct_passwd:
        """
        Return the user record corresponding to the given username.
        """
        if not isinstance(name, str):
            raise TypeError(f"getpwnam() argument must be str, not {type(name)}")
        for entry in self._users:
            if entry.pw_name == name:
                return entry
        raise KeyError(name)

    def getpwall(self) -> list[struct_passwd]:
        """
        Return a list of all user records.
        """
        return self._users


class _ShadowRecord:
    """
    L{_ShadowRecord} holds the shadow user data for a single user in
    L{ShadowDatabase}.  It corresponds to C{spwd.struct_spwd}.  See that class
    for attribute documentation.
    """

    def __init__(
        self,
        username: str,
        password: str,
        lastChange: int,
        min: int,
        max: int,
        warn: int,
        inact: int,
        expire: int,
        flag: int,
    ) -> None:
        self.sp_nam = username
        self.sp_pwd = password
        self.sp_lstchg = lastChange
        self.sp_min = min
        self.sp_max = max
        self.sp_warn = warn
        self.sp_inact = inact
        self.sp_expire = expire
        self.sp_flag = flag

    def __len__(self) -> int:
        return 9

    def __getitem__(self, index):
        return (
            self.sp_nam,
            self.sp_pwd,
            self.sp_lstchg,
            self.sp_min,
            self.sp_max,
            self.sp_warn,
            self.sp_inact,
            self.sp_expire,
            self.sp_flag,
        )[index]


class ShadowDatabase:
    """
    L{ShadowDatabase} holds a shadow user database in memory and makes it
    available via the same API as C{spwd}.

    @ivar _users: A C{list} of L{_ShadowRecord} instances holding all user data
        added to this database.

    @since: 12.0
    """

    _users: list[_ShadowRecord]

    def __init__(self) -> None:
        self._users = []

    def addUser(
        self,
        username: str,
        password: str,
        lastChange: int,
        min: int,
        max: int,
        warn: int,
        inact: int,
        expire: int,
        flag: int,
    ) -> None:
        """
        Add a new user record to this database.

        @param username: The value for the C{sp_nam} field of the user record to
            add.

        @param password: The value for the C{sp_pwd} field of the user record to
            add.

        @param lastChange: The value for the C{sp_lstchg} field of the user
            record to add.

        @param min: The value for the C{sp_min} field of the user record to add.

        @param max: The value for the C{sp_max} field of the user record to add.

        @param warn: The value for the C{sp_warn} field of the user record to
            add.

        @param inact: The value for the C{sp_inact} field of the user record to
            add.

        @param expire: The value for the C{sp_expire} field of the user record
            to add.

        @param flag: The value for the C{sp_flag} field of the user record to
            add.
        """
        self._users.append(
            _ShadowRecord(
                username, password, lastChange, min, max, warn, inact, expire, flag
            )
        )

    def getspnam(self, username: str) -> _ShadowRecord:
        """
        Return the shadow user record corresponding to the given username.
        """
        if not isinstance(username, str):
            raise TypeError(f"getspnam() argument must be str, not {type(username)}")
        for entry in self._users:
            if entry.sp_nam == username:
                return entry
        raise KeyError(username)

    def getspall(self):
        """
        Return a list of all shadow user records.
        """
        return self._users
