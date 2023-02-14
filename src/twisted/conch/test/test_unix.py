# -*- test-case-name: twisted.conch.test.test_unix -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from zope.interface import implementer

from twisted.conch.interfaces import IConchUser
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.cred.credentials import IUsernamePassword, UsernamePassword
from twisted.cred.portal import Portal
from twisted.internet.interfaces import IReactorProcess
from twisted.python.fakepwd import UserDatabase
from twisted.python.reflect import requireModule
from twisted.trial import unittest
from .test_session import StubClient, StubConnection

cryptography = requireModule("cryptography")
unix = requireModule("twisted.conch.unix")

if unix is not None:
    from twisted.conch.unix import UnixConchUser, UnixSSHRealm


@implementer(IReactorProcess)
class MockProcessSpawner:
    """
    An L{IReactorProcess} that logs calls to C{spawnProcess}.
    """

    def __init__(self):
        self._spawnProcessCalls = []

    def spawnProcess(
        self,
        processProtocol,
        executable,
        args=(),
        env={},
        path=None,
        uid=None,
        gid=None,
        usePTY=0,
        childFDs=None,
    ):
        """
        Log a call to C{spawnProcess}. Do not actually spawn a process.
        """
        self._spawnProcessCalls.append(
            {
                "processProtocol": processProtocol,
                "executable": executable,
                "args": args,
                "env": env,
                "path": path,
                "uid": uid,
                "gid": gid,
                "usePTY": usePTY,
                "childFDs": childFDs,
            }
        )


class TestSSHSessionForUnixConchUser(unittest.TestCase):

    if cryptography is None:
        skip = "Cannot run without cryptography"
    elif unix is None:
        skip = "Unix system required"

    def testExecCommandEnvironment(self) -> None:
        """
        C{execCommand} sets the C{HOME} environment variable to the avatar's home
        directory.
        """
        userdb = UserDatabase()
        homeDirectory = "/made/up/path/"
        userName = "user"
        userdb.addUser(userName, home=homeDirectory)
        self.patch(unix, "pwd", userdb)
        mockReactor = MockProcessSpawner()
        avatar = UnixConchUser(userName)
        avatar.conn = StubConnection(transport=StubClient())
        session = unix.SSHSessionForUnixConchUser(avatar, reactor=mockReactor)
        protocol = None
        command = ["not-actually-executed"]
        session.execCommand(protocol, command)
        [call] = mockReactor._spawnProcessCalls
        self.assertEqual(homeDirectory, call["env"]["HOME"])


class TestUnixSSHRealm(unittest.TestCase):
    """
    Tests for L{UnixSSHRealm}.
    """

    def test_unixSSHRealm(self) -> None:
        """
        L{UnixSSHRealm} is an L{IRealm} whose C{.requestAvatar} method returns
        a L{UnixConchUser}.
        """
        userdb = UserDatabase()
        home = "/testing/home/value"
        userdb.addUser("user", home=home)
        self.patch(unix, "pwd", userdb)
        pwdb = InMemoryUsernamePasswordDatabaseDontUse(user=b"password")
        p = Portal(UnixSSHRealm(), [pwdb])

        # there seems to be a bug in mypy-zope where sometimes things don't
        # implement their superinterfaces; 0.3.11, when we upgrade to 0.9.0
        # this type declaration will be extraneous
        creds: IUsernamePassword = UsernamePassword(b"user", b"password")
        result = p.login(creds, None, IConchUser)
        resultInterface, avatar, logout = self.successResultOf(result)
        self.assertIsInstance(avatar, UnixConchUser)
        assert isinstance(avatar, UnixConchUser)  # legibility for mypy
        self.assertEqual(avatar.getHomeDir(), home)
