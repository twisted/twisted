# -*- test-case-name: twisted.protocols._smb.tests -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""Implement Microsoft's Server Message Block protocol"""

import struct
import binascii
import uuid
import time
from collections import namedtuple

from twisted.protocols._smb import base, security_blob
from twisted.protocols._smb.interfaces import (ISMBServer, IFilesystem, IPipe,
                                               IPrinter)

from twisted.internet import protocol
from twisted.logger import Logger
from twisted.cred.checkers import ANONYMOUS
from twisted.internet.defer import maybeDeferred

log = Logger()

SMBMind = namedtuple('SMBMind', 'session_id domain addr')

COMMANDS = [
    ('negotiate',
     base.nstruct("""
     size:H dialect_count:H security_mode:H
        reserved:H capabilities:I client_uuid:16s"""),
     base.nstruct("""size:H signing:H dialect:H reserved:H  server_uuid:16s
       capabilities:I max_transact:I max_read:I max_write:I time:Q
       boot_time:Q offset:H buflen:H reserved2:I""")),
    ('session_setup',
     base.nstruct("""size:H flags:B security_mode:B
     capabilities:I channel:I offset:H buflen:H prev_session_id:Q"""),
     base.nstruct("size:H flags:H offset:H buflen:H")),
    ('logoff', base.nstruct("size:H reserved:H"),
     base.nstruct("size:H reserved:H")),
    ('tree_connect', base.nstruct("size:H reserved:H offset:H buflen:H"),
     base.nstruct("""size:H share_type:B reserved:B flags:I capabilities:I
       max_perms:I""")),
    ('tree_disconnect', base.nstruct("size:H reserved:H"),
     base.nstruct("size:H reserved:H"))
]

# the complete list of NT statuses is very large, so just
# add those actually used
STATUS_SUCCESS = 0x00
STATUS_MORE_PROCESSING = 0xC0000016
STATUS_NO_SUCH_FILE = 0xC000000F
STATUS_UNSUCCESSFUL = 0xC0000001
STATUS_NOT_IMPLEMENTED = 0xC0000002
STATUS_INVALID_HANDLE = 0xC0000008
STATUS_ACCESS_DENIED = 0xC0000022
STATUS_END_OF_FILE = 0xC0000011
STATUS_DATA_ERROR = 0xC000003E
STATUS_QUOTA_EXCEEDED = 0xC0000044
STATUS_FILE_LOCK_CONFLICT = 0xC0000054  # generated on read/writes
STATUS_LOCK_NOT_GRANTED = 0xC0000055  # generated when requesting lock
STATUS_LOGON_FAILURE = 0xC000006D
STATUS_DISK_FULL = 0xC000007F
STATUS_ACCOUNT_RESTRICTION = 0xC000006E
STATUS_PASSWORD_EXPIRED = 0xC0000071
STATUS_ACCOUNT_DISABLED = 0xC0000072
STATUS_FILE_INVALID = 0xC0000098
STATUS_DEVICE_DATA_ERROR = 0xC000009C
STATUS_BAD_NETWORK_NAME = 0xC00000CC  # = "share not found"

FLAG_SERVER = 0x01
FLAG_ASYNC = 0x02
FLAG_RELATED = 0x04
FLAG_SIGNED = 0x08
FLAG_PRIORITY_MASK = 0x70
FLAG_DFS_OPERATION = 0x10000000
FLAG_REPLAY_OPERATION = 0x20000000

NEGOTIATE_SIGNING_ENABLED = 0x0001
NEGOTIATE_SIGNING_REQUIRED = 0x0002

MAX_READ_SIZE = 0x10000
MAX_TRANSACT_SIZE = 0x10000
MAX_WRITE_SIZE = 0x10000

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
        self.is_async = False
        self.is_related = False
        self.is_signed = False
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
        protocol_id = packet[:4]
        if protocol_id == b"\xFFSMB":
            # its a SMB1 packet which we dont support with the exception
            # of the first packet, we try to offer upgrade to SMB2
            if self.avatar is None:
                log.debug("responding to SMB1 packet")
                self.negotiate_response()
            else:
                self.transport.close()
                log.error("Got SMB1 packet while logged in")
            return
        elif protocol_id != b"\xFESMB":
            self.transport.close()
            log.error("Unknown packet type")
            log.debug("packet data {data!r}", data=packet[:64])
            return
        begin_struct = "<4xHH4sHHLLQ"
        (hdr_size, self.credit_charge, hdr_status, self.hdr_command,
         self.credit_request, self.hdr_flags, self.next_command,
         self.message_id) = struct.unpack(begin_struct, packet[:32])
        self.is_async = (self.hdr_flags & FLAG_ASYNC) > 0
        self.is_related = (self.hdr_flags & FLAG_RELATED) > 0
        self.is_signed = (self.hdr_flags & FLAG_SIGNED) > 0
        # FIXME other flags 3.1 or too obscure
        if self.is_async:
            (self.async_id, self.session_id,
             self.signature) = struct.unpack("<QQ16s", packet[32:64])
            self.tree_id = 0x00
        else:
            (_reserved, self.tree_id, self.session_id,
             self.signature) = struct.unpack("<LLQ16s", packet[32:64])
            self.async_id = 0x00
        log.debug("HEADER")
        log.debug("------")
        log.debug("protocol ID     {pid!r}", pid=protocol_id)
        log.debug("size            {hs}", hs=hdr_size)
        log.debug("credit charge   {cc}", cc=self.credit_charge)
        log.debug("status          {status}", status=hdr_status)
        log.debug("command         {cmd!r} {cmdn:02x}",
                  cmd=COMMANDS[self.hdr_command],
                  cmdn=self.hdr_command)
        log.debug("credit request  {cr}", cr=self.credit_request)
        s = ""
        if self.is_async:
            s += "ASYNC "
        if self.is_signed:
            s += "SIGNED "
        if self.is_related:
            s += "RELATED "
        log.debug("flags           0x{flags:x} {s}", flags=self.hdr_flags, s=s)
        log.debug("next command    0x{nc:x}", nc=self.next_command)
        log.debug("message ID      0x{mid:x}", mid=self.message_id)
        log.debug("session ID      0x{sid:x}", sid=self.session_id)
        if self.is_async:
            log.debug("async ID        0x{aid:x}", aid=self.async_id)
        else:
            log.debug("tree ID         0x{tid:x}", tid=self.tree_id)
        log.debug("signature       {sig}",
                  sig=binascii.hexlify(self.signature))
        try:
            name, req_type, resp_type = COMMANDS[self.hdr_command]
        except IndexError:
            log.error("unknown command 0x{cmd:x}", cmd=self.hdr_command)
            self.error_response(STATUS_NOT_IMPLEMENTED)
        else:
            func = 'smb_' + name
            try:
                if hasattr(self, func) and req_type:
                    req = req_type(packet[64:])
                    resp = resp_type()
                    getattr(self, func)(req, resp)
                else:
                    log.error("command '{cmd}' not implemented",
                              cmd=COMMANDS[self.hdr_command][0])
                    self.error_response(STATUS_NOT_IMPLEMENTED)
            except base.SMBError as e:
                log.error(str(e))
                self.error_response(e.ntstatus)
            except BaseException:
                log.failure("in {cmd}", cmd=COMMANDS[self.hdr_command][0])
                self.error_response(STATUS_UNSUCCESSFUL)
        if self.is_related and self.next_command > 0:
            self.packetReceived(packet[self.next_command:])

    def send_with_header(self, payload, command=None, status=STATUS_SUCCESS):
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
        payload = bytes(payload)
        # FIXME credit and signatures not supportted
        flags = FLAG_SERVER
        if self.is_async:
            flags |= FLAG_ASYNC
        if command is None:
            command = self.hdr_command
        elif isinstance(command, str):
            cmds = [c[0] for c in COMMANDS]
            command = cmds.index(command)
        header_data = struct.pack("<4sHHLHHLLQ", b'\xFESMB', 64, 0, status,
                                  command, 1, flags, 0, self.message_id)
        if self.is_async:
            header_data += struct.pack("<QQ16x", self.async_id,
                                       self.session_id)
        else:
            header_data += struct.pack("<LLQ16x", 0, self.tree_id,
                                       self.session_id)
        self.sendPacket(header_data + payload)

    def smb_negotiate(self, req, resp):
        # capabilities is ignored as a 3.1 feature
        # as are final field complex around "negotiate contexts"
        self.client_uuid = uuid.UUID(bytes_le=req.client_uuid)
        dialects = struct.unpack(
            "<%dH" % req.dialect_count,
            req.buffer[req.size - len(req):req.size - len(req) +
                       (req.dialect_count * 2)])
        self.signing_enabled = (req.security_mode
                                & NEGOTIATE_SIGNING_ENABLED) > 0
        # by spec this should never be false
        self.signing_required = (req.security_mode
                                 & NEGOTIATE_SIGNING_REQUIRED) > 0
        log.debug("NEGOTIATE")
        log.debug("---------")
        log.debug("size            {sz}", sz=req.size)
        log.debug("dialect count   {dc}", dc=req.dialect_count)
        s = ""
        if self.signing_enabled:
            s += "ENABLED "
        if self.signing_required:
            s += "REQUIRED"
        log.debug("signing         0x{sm:02x} {s}", sm=req.security_mode, s=s)
        log.debug("client UUID     {uuid}", uuid=self.client_uuid)
        log.debug("dialects        {dlt!r}",
                  dlt=["%04x" % x for x in dialects])
        self.negotiate_response(dialects)

    def error_response(self, ntstatus):
        self.send_with_header(b'\x09\0\0\0\0\0\0\0', status=ntstatus)
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
        resp = COMMANDS[0][2]()
        resp.size = 65
        resp.signing = NEGOTIATE_SIGNING_ENABLED
        resp.dialect = self.dialect
        resp.server_uuid = self.factory.server_uuid.bytes_le
        resp.capabilities = GLOBAL_CAP_DFS
        resp.max_transact = MAX_TRANSACT_SIZE
        resp.max_read = MAX_READ_SIZE
        resp.max_write = MAX_WRITE_SIZE
        resp.time = base.u2nt_time(time.time())
        resp.boot_time = base.u2nt_time(self.factory.server_start)
        resp.offset = 128
        resp.buflen = len(blob)
        resp.buffer = blob
        self.send_with_header(resp, 'negotiate')

    def smb_session_setup(self, req, resp):
        blob = req.buffer[req.offset - len(req) - 64:req.offset - len(req) -
                          64 + req.buflen]
        log.debug("SESSION SETUP")
        log.debug("-------------")
        log.debug("Size             {sz}", sz=req.size)
        log.debug("Security mode    0x{sm:08x}", sm=req.security_mode)
        log.debug("Capabilities     0x{cap:08x}", cap=req.capabilities)
        log.debug("Channel          0x{chl:08x}", chl=req.channel)
        log.debug("Prev. session ID 0x{pid:016x}", pid=req.prev_session_id)
        if self.first_session_setup:
            self.blob_manager.receiveInitialBlob(blob)
            resp.buffer = self.blob_manager.generateChallengeBlob()
            self.session_setup_response(resp, STATUS_MORE_PROCESSING)
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
                d.addCallback(self._cb_login, resp)
                d.addErrback(self._eb_login, resp)
            else:
                resp.buffer = self.blob_manager.generateChallengeBlob()
                self.session_setup_response(resp, STATUS_MORE_PROCESSING)

    def _cb_login(self, t, resp):
        _, self.avatar, self.logout_thunk = t
        resp.buffer = self.blob_manager.generateAuthResponseBlob(True)
        log.debug("successful login")
        self.session_setup_response(resp, STATUS_SUCCESS)

    def _eb_login(self, failure, resp):
        log.debug(failure.getTraceback())
        resp.buffer = self.blob_manager.generateAuthResponseBlob(False)
        self.session_setup_response(resp, STATUS_LOGON_FAILURE)

    def session_setup_response(self, resp, ntstatus):
        log.debug("session_setup_response")
        resp.flags = 0
        if self.blob_manager.credential == ANONYMOUS:
            resp.flags |= SESSION_FLAG_IS_NULL
        resp.size = 9
        resp.offset = 72
        resp.buflen = len(resp.buffer)
        self.send_with_header(resp, 'session_setup', ntstatus)

    def smb_logoff(self, req, resp):
        assert req.size == 4
        resp.size = 4
        self.send_with_header(resp)
        if self.logout_thunk:
            d = maybeDeferred(self.logout_thunk)
            d.addErrback(self._eb_logoff)

    def _eb_logoff(self, f):
        log.error(f.getTraceback())

    def smb_tree_connect(self, req, resp):
        if self.avatar is None:
            self.error_response(STATUS_ACCESS_DENIED)
            return
        assert req.size == 9
        path = req.buffer[req.offset - len(req) - 64:req.offset - len(req) -
                          64 + req.buflen]
        path = path.decode("utf-16le").split("\\")[-1]
        try:
            share = self.avatar.getShare(path)
        except KeyError:
            self.error_response(STATUS_BAD_NETWORK_NAME)
            return
        if IFilesystem.providedBy(share):
            resp.share_type = SHARE_DISK
            # FUTURE: select these values from share object
            resp.flags = SHAREFLAG_MANUAL_CACHING
            resp.capabilities = 0
            resp.max_perms = (FILE_READ_DATA | FILE_WRITE_DATA
                              | FILE_APPEND_DATA | FILE_READ_EA | FILE_WRITE_EA
                              | FILE_DELETE_CHILD | FILE_EXECUTE
                              | FILE_READ_ATTRIBUTES | FILE_WRITE_ATTRIBUTES
                              | DELETE | READ_CONTROL | WRITE_DAC | WRITE_OWNER
                              | SYNCHRONIZE)
        elif IPipe.providedBy(share):
            resp.share_type = SHARE_PIPE
            resp.flags = 0
            resp.max_perms = (
                FILE_READ_DATA | FILE_WRITE_DATA | FILE_APPEND_DATA
                | FILE_READ_EA |
                # FILE_WRITE_EA |
                # FILE_DELETE_CHILD |
                FILE_EXECUTE | FILE_READ_ATTRIBUTES |
                # FILE_WRITE_ATTRIBUTES |
                DELETE | READ_CONTROL |
                # WRITE_DAC |
                # WRITE_OWNER |
                SYNCHRONIZE)
        elif IPrinter.providedBy(share):
            resp.share_type = SHARE_PRINTER
            resp.flags = 0
            # FIXME need to check printer  max perms
            resp.max_perms = (
                FILE_READ_DATA | FILE_WRITE_DATA | FILE_APPEND_DATA
                | FILE_READ_EA |
                # FILE_WRITE_EA |
                # FILE_DELETE_CHILD |
                FILE_EXECUTE | FILE_READ_ATTRIBUTES |
                # FILE_WRITE_ATTRIBUTES |
                DELETE | READ_CONTROL |
                # WRITE_DAC |
                # WRITE_OWNER |
                SYNCHRONIZE)
        else:
            log.error("unknown share object {share!r}", share=share)
            self.error_response(STATUS_UNSUCCESSFUL)
            return
        resp.size = 16
        self.tree_id = base.int32key(self.trees, share)
        self.send_with_header(resp)

    def smb_tree_disconnect(self, req, resp):
        assert req.size == 4
        del self.trees[self.tree_id]
        resp.size = 4
        self.send_with_header(resp)



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
        self.server_uuid = uuid.uuid4()
        self.server_start = time.time()

    def buildProtocol(self, addr):
        return SMBConnection(self, addr)
