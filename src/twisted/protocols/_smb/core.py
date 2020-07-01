# -*- test-case-name: twisted.protocols._smb.tests -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""Implement Microsoft's Server Message Block protocol"""

import struct
import binascii
from uuid import uuid4
import time
from collections import namedtuple
import enum
import attr

from twisted.protocols._smb import base, security_blob
from twisted.protocols._smb.base import (byte, short, medium, long, uuid)
from twisted.protocols._smb.ismb import (ISMBServer, IFilesystem, IPipe,
                                         IPrinter, NoSuchShare)

from twisted.internet import protocol
from twisted.logger import Logger
from twisted.cred.checkers import ANONYMOUS
from twisted.internet.defer import maybeDeferred

log = Logger()

SMBMind = namedtuple('SMBMind', 'session_id domain addr')



@attr.s
class NegReq:
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
    size = short(9, locked=True)
    flags = short()
    offset = short(72, locked=True)
    buflen = short()



@attr.s
class BasicPacket:
    size = short(4, locked=True)
    reserved = short()



@attr.s
class TreeReq:
    size = short(9, locked=True)
    reserved = short()
    offset = short()
    buflen = short()



@attr.s
class TreeResp:
    size = short(16, locked=True)
    share_type = byte()
    reserved = byte()
    flags = medium()
    capabilities = medium()
    max_perms = medium()



COMMANDS = [('negotiate', NegReq, NegResp),
            ('session_setup', SessionReq, SessionResp),
            ('logoff', BasicPacket, BasicPacket),
            ('tree_connect', TreeReq, TreeResp),
            ('tree_disconnect', BasicPacket, BasicPacket)]



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

SMB1_MAGIC = b'\xFFSMB'
SMB2_MAGIC = b'\xFESMB'

ERROR_RESPONSE_MAGIC = b'\x09\0\0\0\0\0\0\0'

HEADER_STRUCT = struct.Struct("<4xHH4sHHLLQ")
HEADER_STRUCT_ASYNC = struct.Struct("<QQ16s")
HEADER_STRUCT_SYNC = struct.Struct("<LLQ16s")
HEADER_LEN = HEADER_STRUCT.size + HEADER_STRUCT_SYNC.size



class SMBConnection(base.SMBPacketReceiver):
    """
    implement SMB protocol server-side
    """
    def __init__(self, factory, addr):
        base.SMBPacketReceiver.__init__(self)
        log.debug("new SMBConnection from {addr!r}", addr=addr)
        self.addr = addr
        self.factory = factory
        self.avatar = None
        self.logout_thunk = None
        self.signing_enabled = False
        self.signing_required = False
        self.message_id = 0
        self.tree_id = 0
        self.session_id = 0
        self.async_id = 0
        self.first_session_setup = True
        self.isAsync = False
        self.isRelated = False
        self.isSigned = False
        self.blob_manager = security_blob.BlobManager(factory.domain)
        self.trees = {}

    def packetReceived(self, packet):
        """
        receive a SMB packet with header. Unpacks the
        header then calls the appropriate smb_XXX
        method with data beyond the header.

        @param packet: the raw packet
        @type packet: L{bytes}
        """
        offset = 0
        self.isRelated = True
        while self.isRelated:
            protocol_id = packet[offset:offset + len(SMB2_MAGIC)]
            if protocol_id == SMB1_MAGIC:
                # its a SMB1 packet which we dont support with the exception
                # of the first packet, we try to offer upgrade to SMB2
                if self.avatar is None:
                    log.debug("responding to SMB1 packet")
                    self.negotiate_response()
                else:
                    self.transport.close()
                    log.error("Got SMB1 packet while logged in")
                return
            elif protocol_id != SMB2_MAGIC:
                self.transport.close()
                log.error("Unknown packet type")
                log.debug("packet data {data!r}",
                          data=packet[offset:offset + 64])
                return
            (hdr_size, self.credit_charge, hdr_status, self.hdr_command,
             self.credit_request, self.hdr_flags, self.next_command,
             self.message_id) = HEADER_STRUCT.unpack_from(packet, offset)
            o2 = offset + HEADER_STRUCT.size
            self.isAsync = (self.hdr_flags & FLAG_ASYNC) > 0
            self.isRelated = (self.hdr_flags & FLAG_RELATED) > 0
            self.isSigned = (self.hdr_flags & FLAG_SIGNED) > 0
            # FIXME other flags 3.1 or too obscure
            if self.isAsync:
                (self.async_id, self.session_id,
                 self.signature) = HEADER_STRUCT_ASYNC.unpack_from(packet, o2)
                o2 += HEADER_STRUCT_ASYNC.size
                self.tree_id = 0x00
            else:
                (_reserved, self.tree_id, self.session_id,
                 self.signature) = HEADER_STRUCT_SYNC.unpack_from(packet, o2)
                o2 += HEADER_STRUCT_SYNC.size
                self.async_id = 0x00
            if self.isRelated:
                this_packet = packet[offset:offset + self.next_command]
            else:
                this_packet = packet[offset:]
            flags_desc = ""
            if self.isAsync:
                flags_desc += " ASYNC"
            if self.isRelated:
                flags_desc += " RELATED"
            if self.isSigned:
                flags_desc += " SIGNED"
            log.debug("""
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
                      hs=hdr_size,
                      cc=self.credit_charge,
                      status=hdr_status,
                      cmd=COMMANDS[self.hdr_command][0],
                      cmdn=self.hdr_command,
                      cr=self.credit_request,
                      flags=self.hdr_flags,
                      flags_desc=flags_desc,
                      nc=self.next_command,
                      mid=self.message_id,
                      sid=self.session_id,
                      aid=self.async_id,
                      tid=self.tree_id,
                      sig=binascii.hexlify(self.signature))
            if self.hdr_command < len(COMMANDS):
                name, req_type, resp_type = COMMANDS[self.hdr_command]
                func = 'smb_' + name
                try:
                    if hasattr(self, func) and req_type:
                        req = base.unpack(req_type, packet, o2)
                        getattr(self, func)(this_packet, req, resp_type)
                    else:
                        log.error("command '{cmd}' not implemented",
                                  cmd=COMMANDS[self.hdr_command][0])
                        self.error_response(NTStatus.NOT_IMPLEMENTED)
                except base.SMBError as e:
                    log.error("SMB error: {e}", e=str(e))
                    self.error_response(e.ntstatus)
                except BaseException:
                    log.failure("in {cmd}", cmd=COMMANDS[self.hdr_command][0])
                    self.error_response(NTStatus.UNSUCCESSFUL)
            else:
                log.error("unknown command 0x{cmd:x}", cmd=self.hdr_command)
                self.error_response(NTStatus.NOT_IMPLEMENTED)

            offset += self.next_command

    def send_with_header(self, payload, command=None, status=NTStatus.SUCCESS):
        """
        prepare and transmit a SMB header and payload
        so a full packet but focus of function on header construction

        @param command: command name or id, defaults to same as received packet
        @type command: L{str} or L{int}

        @param payload: the after-header data
        @type payload: L{bytes}

        @param status: packet status, an NTSTATUS code
        @type status: L{int}
        """
        # FIXME credit and signatures not supportted
        flags = FLAG_SERVER
        if self.isAsync:
            flags |= FLAG_ASYNC
        if command is None:
            command = self.hdr_command
        elif isinstance(command, str):
            cmds = [c[0] for c in COMMANDS]
            command = cmds.index(command)
        if isinstance(status, NTStatus):
            status = status.value
        header_data = struct.pack("<4sHHLHHLLQ", SMB2_MAGIC, HEADER_LEN, 0,
                                  status, command, 1, flags, 0,
                                  self.message_id)
        if self.isAsync:
            header_data += struct.pack("<QQ16x", self.async_id,
                                       self.session_id)
        else:
            header_data += struct.pack("<LLQ16x", 0, self.tree_id,
                                       self.session_id)
        self.sendPacket(header_data + payload)

    def smb_negotiate(self, packet, req, resp_type):
        # capabilities is ignored as a 3.1 feature
        # as are final field complex around "negotiate contexts"
        dialects = struct.unpack_from("<%dH" % req.dialect_count,
                                      packet,
                                      offset=HEADER_LEN + req.size)
        self.signing_enabled = (req.security_mode
                                & NEGOTIATE_SIGNING_ENABLED) > 0
        # by spec this should never be false
        self.signing_required = (req.security_mode
                                 & NEGOTIATE_SIGNING_REQUIRED) > 0
        self.client_uuid = req.client_uuid
        desc = ""
        if self.signing_enabled:
            desc += "ENABLED "
        if self.signing_required:
            desc += "REQUIRED"
        log.debug("""
NEGOTIATE
---------
size            {sz}
dialect count   {dc}
signing         0x{sm:02x} {desc}
client UUID     {uuid!r}
dialects        {dlt!r}""",
                  sz=req.size,
                  dc=req.dialect_count,
                  sm=req.security_mode,
                  desc=desc,
                  uuid=req.client_uuid,
                  dlt=["%04x" % x for x in dialects])
        self.negotiate_response(dialects)

    def error_response(self, ntstatus):
        if isinstance(ntstatus, NTStatus):
            ntstatus = ntstatus.value
        self.send_with_header(ERROR_RESPONSE_MAGIC, status=ntstatus)
        # pre 3.1.1 no variation in structure

    def negotiate_response(self, dialects=None):
        log.debug("negotiate_response")
        blob = self.blob_manager.generateInitialBlob()
        if dialects is None:
            log.debug("no dialects data, using 0x0202")
            self.dialect = 0x0202
        else:
            self.dialect = sorted(dialects)[0]
            if self.dialect == 0x02FF:
                self.dialect = 0x0202
            if self.dialect > MAX_DIALECT:
                raise base.SMBError(
                    "min client dialect %04x higher than our max %04x" %
                    (self.dialect, MAX_DIALECT))
            log.debug("dialect {dlt:04x} chosen", dlt=self.dialect)
        resp = NegResp()
        resp.signing = NEGOTIATE_SIGNING_ENABLED
        resp.dialect = self.dialect
        resp.server_uuid = self.factory.server_uuid
        resp.capabilities = GLOBAL_CAP_DFS
        resp.time = base.unixToNTTime(time.time())
        resp.boot_time = base.unixToNTTime(self.factory.server_start)
        resp.buflen = len(blob)
        self.send_with_header(base.pack(resp) + blob, 'negotiate')

    def smb_session_setup(self, packet, req, resp_type):
        blob = packet[req.offset:req.offset + req.buflen]
        log.debug("""
SESSION SETUP
-------------
Size             {sz}
Security mode    0x{sm:08x}
Capabilities     0x{cap:08x}
Channel          0x{chl:08x}
Prev. session ID 0x{pid:016x}""",
                  sz=req.size,
                  sm=req.security_mode,
                  cap=req.capabilities,
                  chl=req.channel,
                  pid=req.prev_session_id)
        if self.first_session_setup:
            self.blob_manager.receiveInitialBlob(blob)
            blob = self.blob_manager.generateChallengeBlob()
            self.session_setup_response(blob, NTStatus.MORE_PROCESSING)
            self.first_session_setup = False
        else:
            self.blob_manager.receiveResp(blob)
            if self.blob_manager.credential:
                log.debug("got credential: %r" % self.blob_manager.credential)
                d = self.factory.portal.login(
                    self.blob_manager.credential,
                    SMBMind(req.prev_session_id,
                            self.blob_manager.credential.domain, self.addr),
                    ISMBServer)

                def cb_login(t):
                    _, self.avatar, self.logout_thunk = t
                    blob = self.blob_manager.generateAuthResponseBlob(True)
                    log.debug("successful login")
                    self.session_setup_response(blob, NTStatus.SUCCESS)

                def eb_login(failure):
                    log.debug(failure.getTraceback())
                    blob = self.blob_manager.generateAuthResponseBlob(False)
                    self.session_setup_response(blob, NTStatus.LOGON_FAILURE)

                d.addCallback(cb_login)
                d.addErrback(eb_login)
            else:
                blob = self.blob_manager.generateChallengeBlob()
                self.session_setup_response(blob, NTStatus.MORE_PROCESSING)

    def session_setup_response(self, blob, ntstatus):
        log.debug("session_setup_response")
        resp = SessionResp()
        if self.blob_manager.credential == ANONYMOUS:
            resp.flags |= SESSION_FLAG_IS_NULL
        resp.buflen = len(blob)
        self.send_with_header(
            base.pack(resp) + blob, 'session_setup', ntstatus)

    def smb_logoff(self, packet, req, resp_type):
        self.send_with_header(base.pack(resp_type()))
        if self.logout_thunk:
            d = maybeDeferred(self.logout_thunk)
            d.addErrback(lambda f: log.error(f.getTraceback()))

    def smb_tree_connect(self, packet, req, resp_type):
        if self.avatar is None:
            self.error_response(NTStatus.ACCESS_DENIED)
            return
        path = packet[req.offset:req.offset + req.buflen]
        path = path.decode("utf-16le")
        log.debug("""
TREE CONNECT
------------
Size   {sz}
Path   {path!r}
""",
                  sz=req.size,
                  path=path)
        path = path.split("\\")[-1]
        d = maybeDeferred(self.avatar.getShare, path)

        def eb_tree(failure):
            if failure.check(NoSuchShare):
                self.error_response(NTStatus.BAD_NETWORK_NAME)
            elif failure.check(base.SMBError):
                log.error("SMB error {e}", e=str(failure.value))
                self.error_response(failure.value.ntstatus)
            else:
                log.error(failure.getTraceback())
                self.error_response(NTStatus.UNSUCCESSFUL)

        def cb_tree(share):
            resp = None
            if IFilesystem.providedBy(share):
                resp = resp_type(
                    share_type=SHARE_DISK,
                    # FUTURE: select these values from share object
                    flags=SHAREFLAG_MANUAL_CACHING,
                    capabilities=0,
                    max_perms=(FILE_READ_DATA | FILE_WRITE_DATA
                               | FILE_APPEND_DATA | FILE_READ_EA
                               | FILE_WRITE_EA
                               | FILE_DELETE_CHILD | FILE_EXECUTE
                               | FILE_READ_ATTRIBUTES
                               | FILE_WRITE_ATTRIBUTES
                               | DELETE | READ_CONTROL | WRITE_DAC
                               | WRITE_OWNER
                               | SYNCHRONIZE))
            if IPipe.providedBy(share):
                assert resp is None, "share can only be one type"
                resp = resp_type(
                    share_type=SHARE_PIPE,
                    flags=0,
                    max_perms=(
                        FILE_READ_DATA | FILE_WRITE_DATA | FILE_APPEND_DATA
                        | FILE_READ_EA |
                        # FILE_WRITE_EA |
                        # FILE_DELETE_CHILD |
                        FILE_EXECUTE | FILE_READ_ATTRIBUTES |
                        # FILE_WRITE_ATTRIBUTES |
                        DELETE | READ_CONTROL |
                        # WRITE_DAC |
                        # WRITE_OWNER |
                        SYNCHRONIZE))
            if IPrinter.providedBy(share):
                assert resp is None, "share can only be one type"
                resp = resp_type(
                    share_type=SHARE_PRINTER,
                    flags=0,
                    # FIXME need to check printer  max perms
                    max_perms=(
                        FILE_READ_DATA | FILE_WRITE_DATA | FILE_APPEND_DATA
                        | FILE_READ_EA |
                        # FILE_WRITE_EA |
                        # FILE_DELETE_CHILD |
                        FILE_EXECUTE | FILE_READ_ATTRIBUTES |
                        # FILE_WRITE_ATTRIBUTES |
                        DELETE | READ_CONTROL |
                        # WRITE_DAC |
                        # WRITE_OWNER |
                        SYNCHRONIZE))
            if resp is None:
                log.error("unknown share object {share!r}", share=share)
                self.error_response(NTStatus.UNSUCCESSFUL)
                return
            self.tree_id = base.int32key(self.trees, share)
            self.send_with_header(base.pack(resp))

        d.addCallback(cb_tree)
        d.addErrback(eb_tree)

    def smb_tree_disconnect(self, packet, req, resp_type):
        del self.trees[self.tree_id]
        self.send_with_header(base.pack(resp_type()))



class SMBFactory(protocol.Factory):
    """
    Factory for SMB servers
    """
    def __init__(self, portal, domain="WORKGROUP"):
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

    def buildProtocol(self, addr):
        return SMBConnection(self, addr)
