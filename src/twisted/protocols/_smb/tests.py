#!/usr/bin/python3

import calendar
import io
import os
import re
import socket
import struct
import sys
import unittest as python_unittest
from typing import (
    List,
    Tuple,
    cast,
    Any,
    Union,
    Sequence,
    Optional,
    Dict,
    Match,
    Callable,
    get_type_hints,
)

from zope.interface import implementer

import attr

from twisted.cred import checkers, credentials, portal
from twisted.internet import reactor
from twisted.internet.interfaces import IProcessTransport, IReactorProcess, IReactorTCP
from twisted.internet.defer import Deferred
from twisted.internet.protocol import ProcessProtocol
from twisted.logger import Logger, globalLogBeginner, textFileLogObserver
from twisted.protocols._smb import _base, core, ntlm, security_blob
from twisted.protocols._smb.ntlm import NTLMFlag
from twisted.protocols._smb.ismb import (
    IFilesystem,
    IPipe,
    IPrinter,
    ISMBServer,
    NoSuchShare,
)
from twisted.python.failure import Failure
from twisted.trial import unittest

log = Logger()
observers = [textFileLogObserver(sys.stdout)]
globalLogBeginner.beginLoggingTo(observers)


@attr.s
class FakeStruct:
    one = _base.short()
    two = _base.byte()
    three = _base.single(4.2)
    four = _base.octets(3)
    five = _base.long(424242, locked=True)


@attr.s
class FakeStruct2:
    i = _base.short()
    b = _base.byte()
    s = _base.octets(3)


class TestBase(unittest.TestCase):
    def test_base_pack(self) -> None:
        data = struct.pack("<HBf3sQ", 525, 42, 4.2, b"bob", 424242)
        r = FakeStruct(one=525)  # type: ignore
        r.two = 42
        r.four = b"bob"
        self.assertEqual(_base.pack(r), data)
        with self.assertRaises(AssertionError):
            r = FakeStruct(five=424243)  # type: ignore

    def test_base_calcsize(self) -> None:
        self.assertEqual(_base.calcsize(FakeStruct), 18)
        self.assertEqual(_base.calcsize(FakeStruct2), 6)

    def test_smb_packet_receiver(self) -> None:
        rdata: Optional[_base.SMBPacket] = None

        def recv(x: _base.SMBPacket) -> None:

            rdata = x

        pr = _base.SMBPacketReceiver(recv, {})
        pr.transport = io.BytesIO()  # type: ignore

        # send fake packet
        pr.sendPacket(b"bur ble")
        r = pr.transport.getvalue()  # type: ignore
        self.assertEqual(r, b"\0\0\0\x07bur ble")
        # receive fake packet
        pr.dataReceived(b"\0\0\0\x03abc")
        if rdata is not None:
            self.assertEqual(rdata.data, b"abc")

    def test_int32key(self) -> None:
        d: Dict[int, str] = {}
        n = _base.int32key(d, "123")
        self.assertEqual(d, {n: "123"})
        self.assertIs(type(n), int)
        self.assertTrue(n > 0)
        self.assertTrue(n < 2 ** 32)

    def test_unpack(self) -> None:
        data = b"\x0B\x02\x0Etwisted"
        with self.subTest(remainder=_base.IGNORE):
            r = _base.unpack(FakeStruct2, data, remainder=_base.IGNORE)
            self.assertEqual(r.i, 523)
            self.assertEqual(r.b, 0x0E)
            self.assertEqual(r.s, b"twi")
        with self.subTest(remainder=_base.ERROR):
            with self.assertRaises(_base.SMBError):
                r = _base.unpack(FakeStruct2, data, remainder=_base.ERROR)
        with self.subTest(remainder=_base.OFFSET):
            r, rem = _base.unpack(FakeStruct2, data, remainder=_base.OFFSET)
            self.assertEqual(r.i, 523)
            self.assertEqual(r.b, 0x0E)
            self.assertEqual(r.s, b"twi")
            self.assertEqual(rem, 6)
        with self.subTest(remainder=_base.DATA):
            r, rem = _base.unpack(FakeStruct2, data, remainder=_base.DATA)
            self.assertEqual(r.i, 523)
            self.assertEqual(r.b, 0x0E)
            self.assertEqual(r.s, b"twi")
            self.assertEqual(rem, b"sted")

    def test_unixToNTTime(self) -> None:
        s = b"\x46\x63\xdc\x91\xd2\x29\xd6\x01"
        (nttime,) = struct.unpack("<Q", s)
        # 2020/5/14 09:32:22.101895
        epoch = calendar.timegm((2020, 5, 14, 9, 32, 22, 0, -1, 0)) + 0.101895
        self.assertEqual(_base.unixToNTTime(epoch), nttime)

        s = b"\x24\xba\x1c\x33\x9f\x14\xd6\x01"
        (nttime,) = struct.unpack("<Q", s)
        # 2020/4/17 10:01:44.388458
        epoch = calendar.timegm((2020, 4, 17, 10, 1, 44, 0, -1, 0)) + 0.388458
        self.assertEqual(_base.unixToNTTime(epoch), nttime)


# captured auth packets from Windows 10 <-> Samba session
NEG_PACKET = (
    b"`H\x06\x06+\x06\x01\x05\x05\x02\xa0>0<\xa0\x0e0\x0c"
    + b"\x06\n+\x06\x01\x04\x01\x827\x02\x02\n\xa2*\x04(NTLMSSP\x00\x01"
    + b"\x00\x00\x00\x97\x82\x08\xe2\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    + b"\x00\x00\x00\x00\x00\x00\x00\n\x00\xbaG\x00\x00\x00\x0f"
)

AUTH_PACKET = (
    b"\xa1\x82\x01\xd30\x82\x01\xcf\xa0\x03\n\x01\x01\xa2\x82"
    b"\x01\xb2\x04\x82\x01\xaeNTLMSSP\x00\x03\x00"
    b"\x00\x00\x18\x00\x18\x00\x9e"
    b"\x00\x00\x00\xe8\x00\xe8\x00\xb6\x00"
    b"\x00\x00 \x00 \x00X\x00\x00\x00\x08"
    b"\x00\x08\x00x\x00\x00\x00\x1e\x00\x1e\x00\x80\x00\x00\x00\x10\x00\x10"
    b"\x00\x9e\x01\x00\x00\x15\x82\x88"
    b"\xe2\n\x00\xbaG\x00\x00\x00\x0f\xbe\xde"
    b'\xe7\xedl\x97\xbe\x84\xdb\x06\x87\x8cT.#"M\x00i\x00c\x00r\x00o\x00s\x00'
    b"o\x00f\x00t\x00A\x00c\x00c\x00o\x00u\x00n\x00t\x00u\x00s\x00e\x00r\x00D"
    b"\x00E\x00S\x00K\x00T\x00O\x00P\x00-\x00E\x009\x006\x00H\x00U\x009\x000"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\xfb@EX\xef#t\xfa\xcf@\x12\xe8p\x95Uo"
    b"\x01\x01\x00\x00\x00\x00\x00\x00\xe6\xfdG\xa0\xd2)\xd6\x01/(\xe8\x98."
    b"\xc0\x17\xec\x00\x00\x00\x00\x02\x00\x0e\x00M\x00I\x00N\x00T\x00B\x00O"
    b"\x00X\x00\x01\x00\x0e\x00M\x00I\x00N\x00T\x00B\x00O\x00X\x00\x04\x00"
    b"\x02\x00\x00\x00\x03\x00\x0e\x00m\x00i"
    b"\x00n\x00t\x00b\x00o\x00x\x00\x07"
    b"\x00\x08\x00\xe6\xfdG\xa0\xd2)\xd6\x01\x06\x00\x04\x00\x02\x00\x00\x00"
    b"\x08\x000\x000\x00\x00\x00\x00\x00\x00"
    b"\x00\x01\x00\x00\x00\x00 \x00\x004"
    b"\x89\xe2\xfa]\xaa\xceM\xe7\xda~\xbf\x1eO\x8c/\x14n\xa2SF\x99j\x11_\x1c"
    b"\xfd%m\x7f\x1d(\n\x00\x10\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\t\x00\x18\x00c\x00i\x00f\x00s\x00/\x00m\x00i"
    b"\x00n\x00t\x00b\x00o\x00x\x00\x00\x00\x00\x00\x00\x00\x00\x00\xb9\xc7"
    b"\xa5?\xcc\x1c%\xb3\x867\x1eY?$\x99\x98\xa3\x12\x04\x10\x01\x00\x00\x00"
    b"\x95_\x1e4\x12?\x07x\x00\x00\x00\x00"
)

CHALLENGE = b"&z\xd3>Cu\xdd+"


class TestSecurity(unittest.TestCase):
    def test_negotiate(self) -> None:
        blob_manager = security_blob.BlobManager("DOMAIN")
        blob_manager.receiveInitialBlob(NEG_PACKET)
        flags = (
            NTLMFlag.Negotiate128
            | NTLMFlag.TargetTypeServer
            | NTLMFlag.RequestTarget
            | NTLMFlag.NegotiateVersion
            | NTLMFlag.NegotiateUnicode
            | NTLMFlag.NegotiateAlwaysSign
            | NTLMFlag.NegotiateSign
            | NTLMFlag.Negotiate56
            | NTLMFlag.NegotiateKeyExchange
            | NTLMFlag.NegotiateExtendedSecurity
            | NTLMFlag.NegotiateNTLM
            | NTLMFlag.NegotiateTargetInfo
            | NTLMFlag.NegotiateLanManagerKey
            | NTLMFlag.NegotiateOEM
        )
        log.debug("blob_manager.flags ={flags!r}", flags=blob_manager.manager.flags)
        self.assertEqual(blob_manager.manager.flags, flags)
        self.assertIsNone(blob_manager.manager.client_domain)
        self.assertIsNone(blob_manager.manager.workstation)

    def test_auth(self) -> None:
        blob_manager = security_blob.BlobManager("DOMAIN")
        blob_manager.receiveInitialBlob(NEG_PACKET)
        blob_manager.generateChallengeBlob()
        blob_manager.manager.challenge = CHALLENGE
        blob_manager.receiveResp(AUTH_PACKET)
        if blob_manager.credential is not None:
            self.assertEqual(blob_manager.credential.domain, "MicrosoftAccount")
            self.assertEqual(blob_manager.credential.username, "user")
            self.assertTrue(blob_manager.credential.checkPassword("password"))
            self.assertFalse(blob_manager.credential.checkPassword("wrong"))

    def test_invalid(self) -> None:
        manager = ntlm.NTLMManager("DOMAIN")
        with self.assertRaises(_base.SMBError):
            manager.receiveToken(b"I'm too short")
        with self.assertRaises(AssertionError):
            manager.receiveToken(b"I'm long enough but have an invalid header")
        with self.assertRaises(_base.SMBError):
            manager.receiveToken(
                b"NTLMSSP\x00\xFF\0\0\0invalid message"
                + b"type                             "
            )


@implementer(IFilesystem)
class TestDisc:
    pass


@implementer(ISMBServer)
class TestAvatar:
    def getShare(self, name: str) -> Union[IFilesystem, IPipe, IPrinter]:
        if name == "share":
            return TestDisc()
        else:
            raise NoSuchShare(name)

    def listShares(self) -> List[str]:
        return ["share"]

    session_id: int = 0


@implementer(portal.IRealm)
class TestRealm:
    def requestAvatar(
        self, avatarId: str, mind: core.SMBMind, *interfaces: Any
    ) -> Tuple[type, ISMBServer, Callable[[], None]]:
        log.debug("avatarId={a!r} mind={m!r}", a=avatarId, m=mind)
        return (ISMBServer, TestAvatar(), lambda: None)


class ChatNotFinished(Exception):
    pass


ChatType = List[Tuple[str, Optional[str]]]


class ChatProcess(ProcessProtocol):
    def __init__(self, chat: ChatType, ignoreRCode: bool) -> None:
        self.chat = chat
        self.d: Deferred = Deferred()
        self.matches: List[Match] = []
        self.ignoreRCode = ignoreRCode

    def outReceived(self, bdata: bytes) -> None:
        data = bdata.decode("utf-8")
        if self.chat:
            prompt, reply = self.chat[0]
            m = re.search(prompt, data)
            if m:
                self.matches.append(m)
                if reply:
                    for i in range(1, 10):
                        t = "\\%d" % i
                        if t in reply:
                            reply = reply.replace(t, m.group(i))
                    if self.transport is not None:
                        self.transport.write(reply.encode("utf-8"))
                else:
                    cast(IProcessTransport, self.transport).closeStdin()
                del self.chat[0]

    def errReceived(self, data: bytes) -> None:
        log.debug("STDERR: {data!r}", data=data)

    def processEnded(self, status: Failure) -> None:
        if (not self.ignoreRCode) and status.value.exitCode != 0:
            self.d.errback(status)
        elif self.chat:
            try:
                raise ChatNotFinished()
            except BaseException:
                self.d.errback(Failure())
        else:
            self.d.callback(self.matches)


def spawn(
    chat: ChatType, args: Sequence[str], ignoreRCode: bool = False, usePTY: bool = True
) -> Deferred:
    pro = ChatProcess(chat, ignoreRCode)
    cast(IReactorProcess, reactor).spawnProcess(pro, args[0], args, usePTY=usePTY)  # type: ignore
    return pro.d


TESTPORT = 5445
SMBCLIENT = "/usr/bin/smbclient"


@python_unittest.skipUnless(os.access(SMBCLIENT, os.X_OK), "smbclient unavailable")
class SambaClientTests(unittest.TestCase):
    def setUp(self) -> None:
        # Start the server
        r = TestRealm()
        p = portal.Portal(r)
        users_checker = checkers.InMemoryUsernamePasswordDatabaseDontUse()
        self.username = "user"
        self.password = "test-password"
        users_checker.addUser(self.username, self.password)
        p.registerChecker(users_checker, credentials.IUsernameHashedPassword)
        log.error("reactor type {t}", t=get_type_hints(reactor))
        self.factory = core.SMBFactory(p)
        self.port = port = cast(IReactorTCP, reactor).listenTCP(TESTPORT, self.factory)  # type: ignore
        self.addCleanup(port.stopListening)

    def smbclient(self, chat: ChatType, ignoreRCode: bool = False) -> Deferred:
        return spawn(
            chat,
            [
                SMBCLIENT,
                "\\\\%s\\share" % socket.gethostname(),
                self.password,
                "-m",
                "SMB2",
                "-U",
                self.username,
                "-I",
                "127.0.0.1",
                "-p",
                str(TESTPORT),
                "-d",
                "10",
            ],
            ignoreRCode=ignoreRCode,
            usePTY=True,
        )

    def test_logon(self) -> Deferred:
        return self.smbclient([("session setup ok", None)], ignoreRCode=True)
