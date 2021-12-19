# -*- test-case-name: twisted.protocols._smb.tests -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""Implement the NT Lan Manager (NTLMv2) challenge/response authentication
protocol
 """

import hashlib
import hmac
import socket
import struct
import time

from zope.interface import implementer

import attr

import twisted.cred.credentials
from twisted.logger import Logger
from twisted.protocols._smb import _base
from twisted.protocols._smb._base import byte, long, medium, octets, short
from twisted.python.randbytes import secureRandom

log = Logger()

NTLM_MESSAGES = ["invalid", "negotiate", "challenge", "auth"]
FLAGS = {
    "NegotiateUnicode": 0x00000001,
    "NegotiateOEM": 0x00000002,
    "RequestTarget": 0x00000004,
    "Unknown9": 0x00000008,
    "NegotiateSign": 0x00000010,
    "NegotiateSeal": 0x00000020,
    "NegotiateDatagram": 0x00000040,
    "NegotiateLanManagerKey": 0x00000080,
    "Unknown8": 0x00000100,
    "NegotiateNTLM": 0x00000200,
    "NegotiateNTOnly": 0x00000400,
    "Anonymous": 0x00000800,
    "NegotiateOemDomainSupplied": 0x00001000,
    "NegotiateOemWorkstationSupplied": 0x00002000,
    "Unknown6": 0x00004000,
    "NegotiateAlwaysSign": 0x00008000,
    "TargetTypeDomain": 0x00010000,
    "TargetTypeServer": 0x00020000,
    "TargetTypeShare": 0x00040000,
    "NegotiateExtendedSecurity": 0x00080000,
    "NegotiateIdentify": 0x00100000,
    "Unknown5": 0x00200000,
    "RequestNonNTSessionKey": 0x00400000,
    "NegotiateTargetInfo": 0x00800000,
    "Unknown4": 0x01000000,
    "NegotiateVersion": 0x02000000,
    "Unknown3": 0x04000000,
    "Unknown2": 0x08000000,
    "Unknown1": 0x10000000,
    "Negotiate128": 0x20000000,
    "NegotiateKeyExchange": 0x40000000,
    "Negotiate56": 0x80000000,
}

DEFAULT_FLAGS = {
    "NegotiateUnicode",
    "NegotiateSign",
    "RequestTarget",
    "NegotiateNTLM",
    "NegotiateAlwaysSign",
    "NegotiateExtendedSecurity",
    "NegotiateTargetInfo",
    "NegotiateVersion",
    "Negotiate128",
    "NegotiateKeyExchange",
    "Negotiate56",
}


def flags2set(flags):
    """
    convert C-style flags to Python set

    @param flags: the flags
    @type flags: L{int}

    @rtype: L{set} of L{str}
    """
    r = set()
    for k, v in FLAGS.items():
        if v | flags > 0:
            r.add(k)
    return r


def set2flags(s):
    """
    convert set to C-style flags

    @rtype: L{int}

    @type s: L{set} of L{str}
    """
    flags = 0
    for i in s:
        flags |= FLAGS[i]
    return flags


def avpair(code, data):
    """make an AVPAIR structure
    @param code: the attribute ID
    @type code: L{int}
    @param data: the value
    @type data: L{bytes}, or L{str} which is converted UTF-16
    @rtype: L{bytes}
    """
    if isinstance(data, str):
        data = data.encode("utf-16le")
    elif len(data) % 2 > 0:
        data += b"\0"
    return struct.pack("<HH", code, len(data)) + data


AV_EOL = 0x0000
AV_COMPUTER_NAME = 0x0001
AV_DOMAIN_NAME = 0x0002
# only first three are required
AV_DNS_COMPUTER_NAME = 0x0003
AV_DNS_DOMAIN_NAME = 0x0004
AV_TREE_NAME = 0x0005
AV_FLAGS = 0x0006
AV_TIMESTAMP = 0x0007
AV_SINGLE_HOST = 0x0008
AV_TARGET_NAME = 0x0009
AV_CHANNEL_BINDINGS = 0x000A

SERVER_VERSION = (6, 1, 1)
# major version 6.1 = Vista, roughly speaking what this emulates
PROTOCOL_VERSION = 0x0F

NT_RESP_TYPE = 0x01

MAGIC = b"NTLMSSP\0"


@attr.s
class HeaderType:
    magic = octets(default=MAGIC, locked=True)
    packet_type = medium()


@attr.s
class NegType:
    flags = medium()
    domain_len = short()
    domain_max_len = short()
    domain_offset = medium()
    workstation_len = short()
    workstation_max_len = short()
    workstation_offset = medium()
    v_major = byte()
    v_minor = byte()
    v_build = short()
    reserved = octets(3)
    v_protocol = byte()


@attr.s
class AuthType:
    lmc_len = short()
    lmc_maxlen = short()
    lmc_offset = medium()
    ntc_len = short()
    ntc_maxlen = short()
    ntc_offset = medium()
    domain_len = short()
    domain_maxlen = short()
    domain_offset = medium()
    user_len = short()
    user_maxlen = short()
    user_offset = medium()
    workstation_len = short()
    workstation_max_len = short()
    workstation_offset = medium()
    ersk_len = short()
    ersk_maxlen = short()
    ersk_offset = medium()
    flags = medium()
    v_major = byte()
    v_minor = byte()
    v_build = short()
    reserved = octets(3)
    v_protocol = byte()
    mic = octets(16)


@attr.s
class NtParts:
    response = octets(16)
    resp_type = byte()
    hi_resp_type = byte()
    reserved = octets(6)
    time = long()
    client_challenge = octets(8)
    reserved2 = octets(4)


@attr.s
class ChallengeType:
    target_len = short()
    target_max_len = short()
    target_offset = medium()
    flags = medium()
    challenge = octets(8)
    reserved = octets(8)
    targetinfo_len = short()
    targetinfo_max_len = short()
    targetinfo_offset = medium()
    v_major = byte()
    v_minor = byte()
    v_build = short()
    reserved2 = octets(3)
    v_protocol = byte()


class NTLMManager:
    """
    manage the NTLM subprotocol

    @ivar credential: the user cred, available after the AUTH token received
                      None prior to this
    @type credential: L{IUsernameHashedPassword}
    """

    def __init__(self, domain):
        """
        @param domain: the server NetBIOS domain
        @type domain: L{str}
        """
        self.credential = None
        self.flags = DEFAULT_FLAGS
        self.server_domain = domain

    def receiveToken(self, token):
        """
        receive client token once unpacked from overlying protocol

        @type token: L{bytes}
        """
        self.token = token
        if len(token) < 36:
            log.debug("{tok}", tok=repr(token))
            raise _base.SMBError("token too small")
        hdr, rem = _base.unpack(HeaderType, token, 0, _base.DATA)
        try:
            getattr(self, "ntlm_" + NTLM_MESSAGES[hdr.packet_type])(rem)
        except IndexError:
            raise _base.SMBError("invalid message %d" % hdr.packet_type)

    def ntlm_invalid(self, data):
        raise _base.SMBError("invalid message id 0")

    def ntlm_challenge(self, data):
        raise _base.SMBError("invalid to send NTLM challenge to a server")

    def ntlm_negotiate(self, data):
        neg = _base.unpack(NegType, data)
        flags = flags2set(neg.flags)
        log.debug(
            """
NTLM NEGOTIATE
--------------
Flags           {flags!r}""",
            flags=flags,
        )
        if "NegotiateVersion" in flags:
            log.debug(
                "Version         {major}.{minor} ({build}) {proto:x}",
                major=neg.v_major,
                minor=neg.v_minor,
                build=neg.v_build,
                proto=neg.v_protocol,
            )
        if "NegotiateUnicode" not in flags:
            raise _base.SMBError("clients must use Unicode")
        if "NegotiateOemDomainSupplied" in flags and neg.domain_len > 0:
            self.client_domain = self.token[
                neg.domain_len : neg.domain_len + neg.domain_offset
            ].decode("utf-16le")
            log.debug("Client domain   {cd!r}", cd=self.client_domain)
        else:
            self.client_domain = None
        if "NegotiateOemWorkstationSupplied" in flags and neg.workstation_len > 0:
            self.workstation = self.token[
                neg.workstation_len : neg.workstation_len + neg.workstation_offset
            ].decode("utf-16le")
            log.debug("Workstation     {wkstn!r}", wkstn=self.workstation)
        else:
            self.workstation = None
        self.flags = DEFAULT_FLAGS & flags
        if (
            "NegotiateAlwaysSign" not in self.flags
            and "NegotiateSign" not in self.flags
        ):
            self.flags -= {"Negotiate128", "Negotiate56"}
        if "RequestTarget" in self.flags:
            self.flags.add("TargetTypeServer")

    def getChallengeToken(self):
        """generate NTLM CHALLENGE token

        @rtype: L{bytes}
        """
        header = HeaderType(packet_type=2)
        chal = ChallengeType()
        if "RequestTarget" in self.flags:
            target = socket.gethostname().upper().encode("utf-16le")
        else:
            target = b""
        if "NegotiateTargetInfo" in self.flags:
            targetinfo = (
                avpair(AV_COMPUTER_NAME, socket.gethostname().upper())
                + avpair(AV_DOMAIN_NAME, self.server_domain)
                + avpair(AV_DNS_COMPUTER_NAME, socket.getfqdn())
                + avpair(AV_DNS_DOMAIN_NAME, b"\0\0")
                + avpair(
                    AV_TIMESTAMP, struct.pack("<Q", _base.unixToNTTime(time.time()))
                )
                + avpair(AV_EOL, b"")
            )
        else:
            targetinfo = b""
        if "NegotiateVersion" in self.flags:
            chal.v_protocol = PROTOCOL_VERSION
            chal.v_major, chal.v_minor, chal.v_build = SERVER_VERSION
        chal.challenge = self.challenge = secureRandom(8)
        chal.target_len = chal.target_max_len = len(target)
        chal.target_offset = _base.calcsize(HeaderType) + _base.calcsize(ChallengeType)
        chal.targetinfo_len = chal.targetinfo_max_len = len(targetinfo)
        chal.targetinfo_offset = chal.target_offset + len(target)
        chal.flags = set2flags(self.flags)
        return _base.pack(header) + _base.pack(chal) + target + targetinfo

    def ntlm_auth(self, data):
        # note authentication isn't checked here, it's just unpacked and
        # loaded into the credential object
        a = _base.unpack(AuthType, data)
        flags = flags2set(a.flags)
        lm = {}
        if a.lmc_len > 0:
            raw_lm_response = self.token[a.lmc_offset : a.lmc_offset + a.lmc_len]
            lm["response"], lm["client_challenge"] = struct.unpack(
                "16s8s", raw_lm_response
            )
        nt = {}
        if a.ntc_len > 0:
            raw_nt_response = self.token[a.ntc_offset : a.ntc_offset + a.ntc_len]
            nt["temp"] = raw_nt_response[16:]
            parts, nt["avpairs"] = _base.unpack(NtParts, raw_nt_response, 0, _base.DATA)
            nt["response"] = parts.response
            nt["time"] = parts.time
            nt["client_challenge"] = parts.client_challenge
            if parts.resp_type != NT_RESP_TYPE:
                log.warn("NT response not valid type")
        if not nt and not lm:
            raise _base.SMBError("one of LM challenge or NT challenge must be provided")
        if a.domain_len > 0:
            client_domain = self.token[a.domain_offset : a.domain_offset + a.domain_len]
            client_domain = client_domain.decode("utf-16le")
        else:
            client_domain = None
        if a.user_len > 0:
            user = self.token[a.user_offset : a.user_offset + a.user_len]
            user = user.decode("utf-16le")
        else:
            raise _base.SMBError("username is required")
        if a.workstation_len > 0:
            workstation = self.token[
                a.workstation_offset : a.workstation_offset + a.workstation_len
            ]
            workstation = workstation.decode("utf-16le")
        else:
            workstation = None
        if a.ersk_len > 0 and "NegotiateKeyExchange" in flags:
            ersk = self.token[a.ersk_offset : a.ersk_offset + a.ersk_len]
        else:
            ersk = None
        self.ersk = ersk
        log.debug(
            """
NTLM AUTH
---------
Flags           {flags!r}
User            {user!r}
Workstation     {wrkstn!r}
Client domain   {cd!r}
LM response     {lm!r}
NT response     {nt!r}
ERSK            {ersk!r}
""",
            flags=flags,
            user=user,
            wrkstn=workstation,
            cd=client_domain,
            lm=lm,
            nt=nt,
            ersk=ersk,
        )
        if "NegotiateVersion" in flags:
            log.debug(
                "Version         {major}.{minor} ({build}) {proto:x}",
                major=a.v_major,
                minor=a.v_minor,
                build=a.v_build,
                proto=a.v_protocol,
            )
        self.credential = NTLMCredential(user, client_domain, lm, nt, self.challenge)


@implementer(twisted.cred.credentials.IUsernameHashedPassword)
class NTLMCredential:
    """
    A NTLM credential, unverified initially
    """

    def __init__(self, user, domain, lm, nt, challenge):
        self.username = user
        self.domain = domain
        self.lm = lm
        self.nt = nt
        self.challenge = challenge

    def __repr__(self):
        return f"<NTLMCredential {self.username}/{self.domain}>"

    def checkPassword(self, password):
        # code adapted from pysmb ntlm.py
        d = hashlib.new("md4")
        d.update(password.encode("UTF-16LE"))
        ntlm_hash = d.digest()  # The NT password hash
        # The NTLMv2 password hash. In [MS-NLMP], this is the result of NTOWFv2
        # and LMOWFv2 functions
        response_key = hmac.new(
            ntlm_hash, (self.username.upper() + self.domain).encode("UTF-16LE"), "md5"
        ).digest()
        if self.lm and self.lm["response"] != b"\0" * 16:
            new_resp = hmac.new(
                response_key, self.challenge + self.lm["client_challenge"], "md5"
            ).digest()
            if new_resp != self.lm["response"]:
                return False
        if self.nt:
            new_resp = hmac.new(
                response_key, self.challenge + self.nt["temp"], "md5"
            ).digest()
            if new_resp != self.nt["response"]:
                return False
        assert self.nt or self.lm
        return True
