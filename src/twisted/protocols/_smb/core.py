# -*- test-case-name: twisted.protocols._smb.tests -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""Implement Microsoft's Server Message Block protocol"""

import binascii
import enum
import struct
import time
from collections import namedtuple
from uuid import uuid4
from typing import Tuple, Any, Optional, Sequence, Union, Callable

import attr

from twisted.cred.checkers import ANONYMOUS
from twisted.cred.portal import Portal
from twisted.internet import protocol
from twisted.internet.defer import maybeDeferred
from twisted.internet.interfaces import IAddress
from twisted.python.failure import Failure
from twisted.logger import Logger
from twisted.protocols._smb import _base, security_blob
from twisted.protocols._smb._base import byte, long, medium, octets, short, uuid
from twisted.protocols._smb.ismb import (
    IFilesystem,
    IPipe,
    IPrinter,
    ISMBServer,
    NoSuchShare,
)

log = Logger()

SMBMind = namedtuple("SMBMind", "session_id domain addr")


@attr.s
class NegReq:
    """negotiate request"""

    size = short(36, locked=True)
    dialect_count = short()
    security_mode = short()
    reserved = short()
    capabilities = medium()
    client_uuid = uuid()


MAX_READ_SIZE = 0x10000
MAX_TRANSACT_SIZE = 0x10000
MAX_WRITE_SIZE = 0x10000


@attr.s
class NegResp:
    """negotiate response"""

    size = short(65, locked=True)
    signing = short()
    dialect = short()
    reserved = short()
    server_uuid = uuid()
    capabilities = medium()
    max_transact = medium(MAX_TRANSACT_SIZE)
    max_read = medium(MAX_READ_SIZE)
    max_write = medium(MAX_WRITE_SIZE)
    time = long()
    boot_time = long()
    offset = short(128, locked=True)
    buflen = short()
    reserved2 = medium()


@attr.s
class SessionReq:
    """session setup request"""

    size = short(25, locked=True)
    flags = byte()
    security_mode = byte()
    capabilities = medium()
    channel = medium()
    offset = short()
    buflen = short()
    prev_session_id = long()


@attr.s
class SessionResp:
    """seesion setup response"""

    size = short(9, locked=True)
    flags = short()
    offset = short(72, locked=True)
    buflen = short()


@attr.s
class BasicPacket:
    """structure used in several request/response types"""

    size = short(4, locked=True)
    reserved = short()


@attr.s
class TreeReq:
    """ttee connect request"""

    size = short(9, locked=True)
    reserved = short()
    offset = short()
    buflen = short()


@attr.s
class TreeResp:
    """tree connect response"""

    size = short(16, locked=True)
    share_type = byte()
    reserved = byte()
    flags = medium()
    capabilities = medium()
    max_perms = medium()


COMMANDS = [
    ("negotiate", NegReq, NegResp),
    ("session_setup", SessionReq, SessionResp),
    ("logoff", BasicPacket, BasicPacket),
    ("tree_connect", TreeReq, TreeResp),
    ("tree_disconnect", BasicPacket, BasicPacket),
]


# the complete list of NT statuses is very large, so just
# add those actually used
class NTStatus(enum.Enum):
    SUCCESS = 0x00
    MORE_PROCESSING = 0xC0000016
    NO_SUCH_FILE = 0xC000000F
    UNSUCCESSFUL = 0xC0000001
    NOT_IMPLEMENTED = 0xC0000002
    INVALID_HANDLE = 0xC0000008
    ACCESS_DENIED = 0xC0000022
    END_OF_FILE = 0xC0000011
    DATA_ERROR = 0xC000003E
    QUOTA_EXCEEDED = 0xC0000044
    FILE_LOCK_CONFLICT = 0xC0000054  # generated on read/writes
    LOCK_NOT_GRANTED = 0xC0000055  # generated when requesting lock
    LOGON_FAILURE = 0xC000006D
    DISK_FULL = 0xC000007F
    ACCOUNT_RESTRICTION = 0xC000006E
    PASSWORD_EXPIRED = 0xC0000071
    ACCOUNT_DISABLED = 0xC0000072
    FILE_INVALID = 0xC0000098
    DEVICE_DATA_ERROR = 0xC000009C
    BAD_NETWORK_NAME = 0xC00000CC  # = "share not found"


FLAG_SERVER = 0x01
FLAG_ASYNC = 0x02
FLAG_RELATED = 0x04
FLAG_SIGNED = 0x08
FLAG_PRIORITY_MASK = 0x70
FLAG_DFS_OPERATION = 0x10000000
FLAG_REPLAY_OPERATION = 0x20000000

NEGOTIATE_SIGNING_ENABLED = 0x0001
NEGOTIATE_SIGNING_REQUIRED = 0x0002
1
SESSION_FLAG_IS_GUEST = 0x0001
SESSION_FLAG_IS_NULL = 0x0002
SESSION_FLAG_ENCRYPT_DATA = 0x0004

NEGOTIATE_SIGNING_ENABLED = 0x0001
NEGOTIATE_SIGNING_REQUIRED = 0x0002

GLOBAL_CAP_DFS = 0x00000001
GLOBAL_CAP_LEASING = 0x00000002
GLOBAL_CAP_LARGE_MTU = 0x00000004
GLOBAL_CAP_MULTI_CHANNEL = 0x00000008
GLOBAL_CAP_PERSISTENT_HANDLES = 0x00000010
GLOBAL_CAP_DIRECTORY_LEASING = 0x00000020
GLOBAL_CAP_ENCRYPTION = 0x00000040

MAX_DIALECT = 0x02FF

SHARE_DISK = 0x01
SHARE_PIPE = 0x02
SHARE_PRINTER = 0x03

SHAREFLAG_MANUAL_CACHING = 0x00000000
SHAREFLAG_AUTO_CACHING = 0x00000010
SHAREFLAG_VDO_CACHING = 0x00000020
SHAREFLAG_NO_CACHING = 0x00000030
SHAREFLAG_DFS = 0x00000001
SHAREFLAG_DFS_ROOT = 0x00000002
SHAREFLAG_RESTRICT_EXCLUSIVE_OPENS = 0x00000100
SHAREFLAG_FORCE_SHARED_DELETE = 0x00000200
SHAREFLAG_ALLOW_NAMESPACE_CACHING = 0x00000400
SHAREFLAG_ACCESS_BASED_DIRECTORY_ENUM = 0x00000800
SHAREFLAG_FORCE_LEVELII_OPLOCK = 0x00001000
SHAREFLAG_ENABLE_HASH_V1 = 0x00002000
SHAREFLAG_ENABLE_HASH_V2 = 0x00004000
SHAREFLAG_ENCRYPT_DATA = 0x00008000
SHAREFLAG_IDENTITY_REMOTING = 0x00040000

SHARE_CAP_DFS = 0x00000008
SHARE_CAP_CONTINUOUS_AVAILABILITY = 0x00000010
SHARE_CAP_SCALEOUT = 0x00000020
SHARE_CAP_CLUSTER = 0x00000040
SHARE_CAP_ASYMMETRIC = 0x00000080
SHARE_CAP_REDIRECT_TO_OWNER = 0x00000100

FILE_READ_DATA = 0x00000001
FILE_LIST_DIRECTORY = 0x00000001
FILE_WRITE_DATA = 0x00000002
FILE_ADD_FILE = 0x00000002
FILE_APPEND_DATA = 0x00000004
FILE_ADD_SUBDIRECTORY = 0x00000004
FILE_READ_EA = 0x00000008  # "Extended Attributes"
FILE_WRITE_EA = 0x00000010
FILE_DELETE_CHILD = 0x00000040
FILE_EXECUTE = 0x00000020
FILE_TRAVERSE = 0x00000020
FILE_READ_ATTRIBUTES = 0x00000080
FILE_WRITE_ATTRIBUTES = 0x00000100
DELETE = 0x00010000
READ_CONTROL = 0x00020000
WRITE_DAC = 0x00040000
WRITE_OWNER = 0x00080000
SYNCHRONIZE = 0x00100000
ACCESS_SYSTEM_SECURITY = 0x01000000
MAXIMUM_ALLOWED = 0x02000000
GENERIC_ALL = 0x10000000
GENERIC_EXECUTE = 0x20000000
GENERIC_WRITE = 0x40000000
GENERIC_READ = 0x80000000

SMB1_MAGIC = b"\xFFSMB"
SMB2_MAGIC = b"\xFESMB"

ERROR_RESPONSE_MAGIC = b"\x09\0\0\0\0\0\0\0"

HEADER_STRUCT = struct.Struct("<4xHH4sHHLLQ")
HEADER_STRUCT_ASYNC = struct.Struct("<QQ16s")
HEADER_STRUCT_SYNC = struct.Struct("<LLQ16s")
HEADER_LEN = HEADER_STRUCT.size + HEADER_STRUCT_SYNC.size


@attr.s
class HeaderSync:
    magic = octets(default=SMB2_MAGIC)
    size = short()
    credit_charge = short()
    status = medium()
    command = short()
    credit_request = short()
    flags = medium()
    next_command = medium()
    message_id = long()
    reserved = medium()
    tree_id = medium()
    session_id = long()
    signature = octets(16)
    async_id: int = attr.ib(default=0)


@attr.s
class HeaderAsync:
    magic = octets(default=SMB2_MAGIC)
    size = short()
    credit_charge = short()
    status = medium()
    command = short()
    credit_request = short()
    flags = medium()
    next_command = medium()
    message_id = long()
    async_id = long()
    session_id = long()
    signature = octets(16)
    tree_id: int = attr.ib(default=0)


def packetReceived(packet: _base.SMBPacket) -> None:
    """
    receive a SMB packet with header. Unpacks the
    header then calls the appropriate smb_XXX
    method with data beyond the header.

    @param packet: the raw packet
    @type packet: L{_base.SMBPacket}
    """
    offset = 0
    isRelated = True
    while isRelated:
        protocol_id = packet.data[offset : offset + len(SMB2_MAGIC)]
        if protocol_id == SMB1_MAGIC:
            # its a SMB1 packet which we dont support with the exception
            # of the first packet, we try to offer upgrade to SMB2
            if packet.ctx.get("avatar") is None:
                log.debug("responding to SMB1 packet")
                negotiateResponse(packet)
            else:
                packet.close()
                log.error("Got SMB1 packet while logged in")
            return
        elif protocol_id != SMB2_MAGIC:
            packet.close()
            log.error("Unknown packet type")
            log.debug("packet data {data!r}", data=packet.data[offset : offset + 64])
            return
        packet.hdr, o2 = _base.unpack(HeaderSync, packet.data, offset, _base.OFFSET)
        isAsync = (packet.hdr.flags & FLAG_ASYNC) > 0
        isRelated = (packet.hdr.flags & FLAG_RELATED) > 0
        isSigned = (packet.hdr.flags & FLAG_SIGNED) > 0
        # FIXME other flags 3.1 or too obscure
        if isAsync:
            packet.hdr = _base.unpack(HeaderAsync, packet.data, offset)
        if isRelated:
            this_packet = packet.data[offset : offset + packet.hdr.next_command]
        else:
            this_packet = packet.data[offset:]
        flags_desc = ""
        if isAsync:
            flags_desc += " ASYNC"
        if isRelated:
            flags_desc += " RELATED"
        if isSigned:
            flags_desc += " SIGNED"
        log.debug(
            """
HEADER
------
protocol ID     {pid!r}
size            {hs}
credit charge   {cc}
status          {status}
command         {cmd!r} {cmdn:02x}
credit request  {cr}
flags           0x{flags:04x}{flags_desc}
next command    0x{nc:x}
message ID      0x{mid:x}
session ID      0x{sid:x}
async ID        0x{aid:x}
tree ID         0x{tid:x}
signature       {sig}""",
            pid=protocol_id,
            hs=packet.hdr.size,
            cc=packet.hdr.credit_charge,
            status=packet.hdr.status,
            cmd=COMMANDS[packet.hdr.command][0],
            cmdn=packet.hdr.command,
            cr=packet.hdr.credit_request,
            flags=packet.hdr.flags,
            flags_desc=flags_desc,
            nc=packet.hdr.next_command,
            mid=packet.hdr.message_id,
            sid=packet.hdr.session_id,
            aid=packet.hdr.async_id,
            tid=packet.hdr.tree_id,
            sig=binascii.hexlify(packet.hdr.signature),
        )
        if packet.hdr.command < len(COMMANDS):
            name, req_type, resp_type = COMMANDS[packet.hdr.command]
            func = "smb_" + name
            try:
                if func in globals() and req_type:
                    req = _base.unpack(req_type, packet.data, o2)
                    new_packet = packet.clone(
                        data=this_packet, hdr=packet.hdr, body=req
                    )
                    globals()[func](new_packet, resp_type)
                else:
                    log.error(
                        "command '{cmd}' not implemented",
                        cmd=COMMANDS[packet.hdr.command][0],
                    )
                    errorResponse(packet, NTStatus.NOT_IMPLEMENTED)
            except _base.SMBError as e:
                log.error("SMB error: {e}", e=str(e))
                errorResponse(packet, e.ntstatus)
            except BaseException:
                log.failure("in {cmd}", cmd=COMMANDS[packet.hdr.command][0])
                errorResponse(packet, NTStatus.UNSUCCESSFUL)
        else:
            log.error("unknown command 0x{cmd:x}", cmd=packet.hdr.command)
            errorResponse(packet, NTStatus.NOT_IMPLEMENTED)

        offset += packet.hdr.next_command


def sendHeader(
    packet: _base.SMBPacket,
    command: Optional[Union[int, str]] = None,
    status: Union[NTStatus, int] = NTStatus.SUCCESS,
) -> None:
    """
    prepare and transmit a SMB header and payload
    so actually a full packet but focus of function on header construction

    @param command: command name or id, defaults to same as received packet
    @type command: L{str} or L{int}

    @param packet: the packet, C{data} contains after-header data
    @type packet: L{_base.SMBPacket}

    @param status: packet status, an NTSTATUS code
    @type status: L{int} or L{NTStatus}
    """
    # FIXME credit and signatures not supported yet
    if packet.hdr is None:
        packet.hdr = HeaderSync()
    packet.hdr.flags |= FLAG_SERVER
    packet.hdr.flags &= ~FLAG_RELATED
    if command is not None:
        if isinstance(command, str):
            cmds = [c[0] for c in COMMANDS]
            icommand = cmds.index(command)
        elif isinstance(command, int):
            icommand = command
        packet.hdr.command = icommand
    packet.hdr.status = status
    packet.hdr.credit_request = 1
    packet.data = _base.pack(packet.hdr) + packet.data
    packet.send()


def smb_negotiate(packet: _base.SMBPacket, resp_type: type) -> None:
    # capabilities is ignored as a 3.1 feature
    # as are final field complex around "negotiate contexts"
    dialects = struct.unpack_from(
        "<%dH" % packet.body.dialect_count,
        packet.data,
        offset=_base.calcsize(HeaderSync) + packet.body.size,
    )
    signing_enabled = (packet.body.security_mode & NEGOTIATE_SIGNING_ENABLED) > 0
    # by spec this should never be false
    signing_required = (packet.body.security_mode & NEGOTIATE_SIGNING_REQUIRED) > 0
    desc = ""
    if signing_enabled:
        desc += "ENABLED "
    if signing_required:
        desc += "REQUIRED"
    log.debug(
        """
NEGOTIATE
---------
size            {sz}
dialect count   {dc}
signing         0x{sm:02x} {desc}
client UUID     {uuid!r}
dialects        {dlt!r}""",
        sz=packet.body.size,
        dc=packet.body.dialect_count,
        sm=packet.body.security_mode,
        desc=desc,
        uuid=packet.body.client_uuid,
        dlt=["%04x" % x for x in dialects],
    )
    negotiateResponse(packet, dialects)


def errorResponse(packet: _base.SMBPacket, ntstatus: Union[NTStatus, int]) -> None:
    """
    send SMB error response

    @type packet: L{_base.SMBPacket}
    @type ntstatus: L{int} or L{NTStatus}
    """
    packet.data = ERROR_RESPONSE_MAGIC
    sendHeader(packet, status=ntstatus)
    # pre 3.1.1 no variation in structure


def negotiateResponse(
    packet: _base.SMBPacket, dialects: Optional[Sequence[int]] = None
) -> None:
    """
    send negotiate response

    @type packet: L{_base.SMBPacket}

    @param dialects: dialects offered by client, if C{None}, 2.02 used
    @type dialects: L{list} of L{int}
    """
    log.debug("negotiateResponse")
    blob_manager = packet.ctx["blob_manager"]
    blob = blob_manager.generateInitialBlob()
    if dialects is None:
        log.debug("no dialects data, using 0x0202")
        dialect = 0x0202
    else:
        dialect = sorted(dialects)[0]
        if dialect == 0x02FF:
            dialect = 0x0202
        if dialect > MAX_DIALECT:
            raise _base.SMBError(
                "min client dialect %04x higher than our max %04x"
                % (dialect, MAX_DIALECT)
            )
        log.debug("dialect {dlt:04x} chosen", dlt=dialect)
    resp = NegResp()
    resp.signing = NEGOTIATE_SIGNING_ENABLED
    resp.dialect = dialect
    resp.server_uuid = packet.ctx["factory"].server_uuid
    resp.capabilities = GLOBAL_CAP_DFS
    resp.time = _base.unixToNTTime(time.time())
    resp.boot_time = _base.unixToNTTime(packet.ctx["factory"].server_start)
    resp.buflen = len(blob)
    packet.data = _base.pack(resp) + blob
    sendHeader(packet, "negotiate")


def smb_session_setup(packet: _base.SMBPacket, resp_type: type) -> None:
    blob = packet.data[packet.body.offset : packet.body.offset + packet.body.buflen]
    log.debug(
        """
SESSION SETUP
-------------
Size             {sz}
Security mode    0x{sm:08x}
Capabilities     0x{cap:08x}
Channel          0x{chl:08x}
Prev. session ID 0x{pid:016x}""",
        sz=packet.body.size,
        sm=packet.body.security_mode,
        cap=packet.body.capabilities,
        chl=packet.body.channel,
        pid=packet.body.prev_session_id,
    )
    blob_manager = packet.ctx["blob_manager"]
    if packet.ctx.get("first_session_setup", True):
        blob_manager.receiveInitialBlob(blob)
        blob = blob_manager.generateChallengeBlob()
        sessionSetupResponse(packet, blob, NTStatus.MORE_PROCESSING)
        packet.ctx["first_session_setup"] = False
    else:
        blob_manager.receiveResp(blob)
        if blob_manager.credential:
            log.debug("got credential: %r" % blob_manager.credential)
            d = packet.ctx["factory"].portal.login(
                blob_manager.credential,
                SMBMind(
                    packet.body.prev_session_id,
                    blob_manager.credential.domain,
                    packet.ctx["addr"],
                ),
                ISMBServer,
            )

            def cb_login(t: Tuple[Any, ISMBServer, Callable[[], None]]) -> None:
                _, packet.ctx["avatar"], packet.ctx["logout_thunk"] = t
                blob = blob_manager.generateAuthResponseBlob(True)
                log.debug("successful login")
                sessionSetupResponse(packet, blob, NTStatus.SUCCESS)

            def eb_login(failure: Failure) -> None:
                log.debug(failure.getTraceback())
                blob = blob_manager.generateAuthResponseBlob(False)
                sessionSetupResponse(packet, blob, NTStatus.LOGON_FAILURE)

            d.addCallback(cb_login)
            d.addErrback(eb_login)
        else:
            blob = blob_manager.generateChallengeBlob()
            sessionSetupResponse(packet, blob, NTStatus.MORE_PROCESSING)


def sessionSetupResponse(
    packet: _base.SMBPacket, blob: bytes, ntstatus: Union[NTStatus, int]
) -> None:
    """
    send session setup response

    @type packet: L{_base.SMBPacket}

    @param blob: the security blob to include in the response
    @type blob: L{bytes}

    @param ntstatus: response status
    @type ntstatus: L{NTStatus}
    """
    log.debug("sessionSetupResponse")
    resp = SessionResp()
    if packet.ctx["blob_manager"].credential == ANONYMOUS:
        resp.flags |= SESSION_FLAG_IS_NULL
    resp.buflen = len(blob)
    packet.data = _base.pack(resp) + blob
    sendHeader(packet, "session_setup", ntstatus)


def smb_logoff(packet: _base.SMBPacket, resp_type: type) -> None:
    packet.data = _base.pack(resp_type())
    sendHeader(packet)
    logout_thunk = packet.ctx.get("logout_thunk")
    if logout_thunk:
        d = maybeDeferred(logout_thunk)
        d.addErrback(lambda f: log.error(f.getTraceback()))


def smb_tree_connect(packet: _base.SMBPacket, resp_type: type) -> None:
    avatar = packet.ctx.get("avatar")
    if avatar is None:
        errorResponse(packet, NTStatus.ACCESS_DENIED)
        return
    path = packet.data[
        packet.body.offset : packet.body.offset + packet.body.buflen
    ].decode("utf-16le")
    log.debug(
        """
TREE CONNECT
------------
Size   {sz}
Path   {path!r}
""",
        sz=packet.body.size,
        path=path,
    )
    path = path.split("\\")[-1]
    d = maybeDeferred(avatar.getShare, path)

    def eb_tree(failure: Failure) -> None:
        if failure.check(NoSuchShare):
            errorResponse(packet, NTStatus.BAD_NETWORK_NAME)
        elif failure.check(_base.SMBError):
            log.error("SMB error {e}", e=str(failure.value))
            errorResponse(packet, failure.value.ntstatus)
        else:
            log.error(failure.getTraceback())
            errorResponse(packet, NTStatus.UNSUCCESSFUL)

    def cb_tree(share: Union[IFilesystem, IPipe, IPrinter]) -> None:
        resp = None
        if IFilesystem.providedBy(share):
            resp = resp_type(
                share_type=SHARE_DISK,
                # FUTURE: select these values from share object
                flags=SHAREFLAG_MANUAL_CACHING,
                capabilities=0,
                max_perms=(
                    FILE_READ_DATA
                    | FILE_WRITE_DATA
                    | FILE_APPEND_DATA
                    | FILE_READ_EA
                    | FILE_WRITE_EA
                    | FILE_DELETE_CHILD
                    | FILE_EXECUTE
                    | FILE_READ_ATTRIBUTES
                    | FILE_WRITE_ATTRIBUTES
                    | DELETE
                    | READ_CONTROL
                    | WRITE_DAC
                    | WRITE_OWNER
                    | SYNCHRONIZE
                ),
            )
        if IPipe.providedBy(share):
            assert resp is None, "share can only be one type"
            resp = resp_type(
                share_type=SHARE_PIPE,
                flags=0,
                max_perms=(
                    FILE_READ_DATA
                    | FILE_WRITE_DATA
                    | FILE_APPEND_DATA
                    | FILE_READ_EA
                    |
                    # FILE_WRITE_EA |
                    # FILE_DELETE_CHILD |
                    FILE_EXECUTE
                    | FILE_READ_ATTRIBUTES
                    |
                    # FILE_WRITE_ATTRIBUTES |
                    DELETE
                    | READ_CONTROL
                    |
                    # WRITE_DAC |
                    # WRITE_OWNER |
                    SYNCHRONIZE
                ),
            )
        if IPrinter.providedBy(share):
            assert resp is None, "share can only be one type"
            resp = resp_type(
                share_type=SHARE_PRINTER,
                flags=0,
                # FIXME need to check printer  max perms
                max_perms=(
                    FILE_READ_DATA
                    | FILE_WRITE_DATA
                    | FILE_APPEND_DATA
                    | FILE_READ_EA
                    |
                    # FILE_WRITE_EA |
                    # FILE_DELETE_CHILD |
                    FILE_EXECUTE
                    | FILE_READ_ATTRIBUTES
                    |
                    # FILE_WRITE_ATTRIBUTES |
                    DELETE
                    | READ_CONTROL
                    |
                    # WRITE_DAC |
                    # WRITE_OWNER |
                    SYNCHRONIZE
                ),
            )
        if resp is None:
            log.error("unknown share object {share!r}", share=share)
            errorResponse(packet, NTStatus.UNSUCCESSFUL)
            return
        packet.hdr.tree_id = _base.int32key(packet.ctx["trees"], share)
        packet.data = _base.pack(resp)
        sendHeader(packet)

    d.addCallback(cb_tree)
    d.addErrback(eb_tree)


def smb_tree_disconnect(packet: _base.SMBPacket, resp_type: type) -> None:
    del packet.ctx["trees"][packet.hdr.tree_id]
    packet.data = _base.pack(resp_type())
    sendHeader(packet)


class SMBFactory(protocol.Factory):
    """
    Factory for SMB servers
    """

    def __init__(self, portal: Portal, domain: str = "WORKGROUP") -> None:
        """
        @param portal: the configured portal
        @type portal: L{twisted.cred.portal.Portal}

        @param domain: the server's Windows/NetBIOS domain name
        @type domain: L{str}
        """
        protocol.Factory.__init__(self)
        self.domain = domain
        self.portal = portal
        self.server_uuid = uuid4()
        self.server_start = time.time()

    def buildProtocol(self, addr: IAddress) -> _base.SMBPacketReceiver:
        log.debug("new SMB connection from {addr!r}", addr=addr)
        return _base.SMBPacketReceiver(
            packetReceived,
            dict(
                addr=addr,
                factory=self,
                blob_manager=security_blob.BlobManager(self.domain),
                trees={},
            ),
        )
