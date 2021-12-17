# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
# -*- test-case-name: twisted.protocols._smb.tests -*-
"""
base classes for SMB networking
"""

import struct
import attr
import uuid as uuid_mod

from twisted.internet import protocol
from twisted.logger import Logger
from twisted.python.randbytes import secureRandom

log = Logger()


class SMBError(Exception):
    """SMB specific errors"""

    def __init__(self, msg, ntstatus=0xC0000001):
        self.msg = msg
        self.ntstatus = ntstatus

    def __str__(self):
        return "%s 0x%08x" % (self.msg, self.ntstatus)


def unixToNTTime(epoch):
    """
    Convert UNIX epoch time to NT filestamp
    quoting from spec: The FILETIME structure is a 64-bit value
    that represents the number of 100-nanosecond intervals that
    have elapsed since January 1, 1601, Coordinated Universal Time.

    @param epoch: seconds since 1970-1-1
    @type epoch: L{float}

    @rtype: L{int}
    """
    return int(epoch * 10000000.0) + 116444736000000000


SMB_METADATA = "__smb_metadata"


def default_only(instance, attribute, value):
    """
    C{attrs} validator that only accepts the default
    """
    assert attribute.default == value, "%s: must be %r, got %r" % (
        attribute.name,
        attribute.default,
        value,
    )


def byte(default=0, locked=False):
    """an 8-bit unsigned integer

    wraps L{attr.ib} with appropriate metadata for use with L{pack} and
    L{unpack}

    @param default: the default value
    @param locked: when C{True}, the default is the only valid value
    @type locked: L{bool}
    """
    return attr.ib(
        default=default,
        type=int,
        metadata={SMB_METADATA: "B"},
        validator=default_only if locked else None,
    )


def short(default=0, locked=False):
    """a 16-bit unsigned integer"""
    return attr.ib(
        default=default,
        type=int,
        metadata={SMB_METADATA: "H"},
        validator=default_only if locked else None,
    )


def medium(default=0, locked=False):
    """a 32-bit unsigned integer"""
    return attr.ib(
        default=default,
        type=int,
        metadata={SMB_METADATA: "I"},
        validator=default_only if locked else None,
    )


def long(default=0, locked=False):
    """an 64-bit unsigned integer"""
    return attr.ib(
        default=default,
        type=int,
        metadata={SMB_METADATA: "Q"},
        validator=default_only if locked else None,
    )


def single(default=0.0):
    """a 32-bit float"""
    return attr.ib(default=default, type=float, metadata={SMB_METADATA: "f"})


def double(default=0.0):
    """a 64-bit float"""
    return attr.ib(default=default, type=float, metadata={SMB_METADATA: "d"})


def octets(length=None, default=None, locked=False):
    """
    a group of octets (bytes). Either a length or a default must be given.
    If a length, the default is all zeros, if a default, the length is taken
    from the default.

    @param length: number of bytes
    @type length: L{int}

    @type default: L{bytes}
    """
    assert length or default
    if length is None:
        length = len(default)
    if default is None:
        default = b"\0" * length
    return attr.ib(
        default=default,
        type=bytes,
        metadata={SMB_METADATA: str(length) + "s"},
        validator=default_only if locked else None,
    )


NULL_UUID = uuid_mod.UUID("00000000-0000-0000-0000-000000000000")
NEW_UUID = attr.Factory(uuid_mod.uuid4)


def uuid(default=NULL_UUID, locked=False):
    """a universial unique ID"""
    default = _conv_uuid(default)
    return attr.ib(
        default=default,
        metadata={SMB_METADATA: "16s"},
        type=uuid_mod.UUID,
        converter=_conv_uuid,
        validator=default_only if locked else None,
    )


def _conv_uuid(x):
    if type(x) is str:
        return uuid_mod.UUID(x)
    elif type(x) is bytes:
        return uuid_mod.UUID(bytes_le=x)
    else:
        return x


def pack(obj):
    """
    pack an object into binary data. The object must have been decorated
    with L{attr.s} and the fields set with the appropriate metadata using
    the helpers in this module

    @rtype: L{bytes}
    """
    strct = _get_struct(type(obj))
    args = tuple(_conv_arg(obj, i) for i in smb_fields(type(obj)))
    return strct.pack(*args)


def _conv_arg(obj, attrib):
    val = getattr(obj, attrib.name)
    if type(val) is uuid_mod.UUID:
        val = val.bytes_le
    return val


IGNORE = 0
ERROR = 1
OFFSET = 2
DATA = 3


def unpack(cls, data, offset=0, remainder=IGNORE):
    """
    unpack binary data into an object.

    @param cls: the class, must be decorated with L{attr.s} and have
    members with the appropriate metadata using the helpers from this
    module.
    @type cls: L{type}

    @param data: the data to unpack
    @type data: L{bytes}

    @param remainder: what to do with remaining data if longer than required
    to fill C{cls}
     - C{IGNORE} ignore it
     - C{ERROR} throw a L{SMBError}
     - C{OFFSET} return offset into data
     where remainder begins as second item of tuple
     - C{DATA} return remaining data as second item of tuple
    @type remainder: L{int}

    @param offset: offset into data to begin from
    @type offset: L{int}

    @return: an instance of C{cls}, or a 2-tuple, first item the former,
             second as determined by C{remainder}
    """
    strct = _get_struct(cls)
    if remainder == ERROR and strct.size + offset < len(data):
        raise SMBError("unexpected remaining data")
    ret = strct.unpack_from(data, offset=offset)
    fields = smb_fields(cls)
    assert len(fields) == len(ret)
    kwargs = {}
    for i in range(len(ret)):
        val = ret[i]
        if fields[i].type is uuid_mod.UUID:
            val = uuid_mod.UUID(bytes_le=val)
        kwargs[fields[i].name] = val
    obj = cls(**kwargs)
    if remainder <= ERROR:
        return obj
    elif remainder == OFFSET:
        return (obj, offset + strct.size)
    else:
        return (obj, data[offset + strct.size :])


def smb_fields(cls):
    return [i for i in attr.fields(cls) if SMB_METADATA in i.metadata]


def _get_struct(cls):
    try:
        # we use classes to hold cache of Structs as precompiling is more
        # efficient
        strct = cls._struct
    except AttributeError:
        strct = struct.Struct(
            "<" + "".join(i.metadata[SMB_METADATA] for i in smb_fields(cls))
        )
        cls._struct = strct
    return strct


def calcsize(cls):
    """
    return the size of a structure.
    @param cls: C{attr} decorated class
    @rtype: L{int}
    """
    strct = _get_struct(cls)
    return strct.size


_leint = struct.Struct("<I")


def int32key(d, val):
    """
    generate a new random key for a dictionary
    @param d: dictionary with 32-bit int keys
    @type d: L{dict}
    @param val: new dictionary value
    @rtype: L{int}
    """
    assert len(d) < 0xC0000000  # otherwiae dict so big hard to find keys
    n = 0
    while n == 0 or n in d:
        [n] = _leint.unpack(secureRandom(_leint.size, True))
    d[n] = val
    return n


@attr.s
class SMBPacket:
    """
    A SMB packet as it moves through the system.

    @ivar data: raw data of the packet, both reception and
                transmission.
    @type data: L{bytes}

    @ivar hdr: the parsed header
    @ivar body: the parsed body
    """

    data = attr.ib()
    _proto = attr.ib()
    hdr = attr.ib(default=None)
    body = attr.ib(default=None)

    @property
    def ctx(self):
        """
        the connection context: objects that need to persist scross
        packets
        @rtype: L{dict}
        """
        return self._proto.ctx

    def send(self):
        """
        transmit the packet's data
        """
        self._proto.sendPacket(self.data)

    def close(self):
        """
        close the underlying connection
        """
        self._proto.transport.close()

    def clone(self, **kwargs):
        """
        a new packet associated with the same connection
        @rtype: L{SMBPacket}
        """
        kwargs["proto"] = self._proto
        return SMBPacket(**kwargs)


BASE_HEADER = struct.Struct("!xBH")


class SMBPacketReceiver(protocol.Protocol):
    """
    A L{SMBPacketReceiver} is a wire protocol parser for the SMB framing
    mechanism, which consist of a 4-byte header: single null
    and a 24-bit length field.
    """

    def __init__(self, packetReceived, ctx):
        """
        @param ctx: context objects for connection
        @type ctx: L{dict}

        @param packetReceived: callback receives each incoming L{SMBPacket}
        @type packetReceived: C{callable}
        """
        self.data = b""
        self.ctx = ctx
        self.packetReceived = packetReceived

    def dataReceived(self, data):
        self.data += data
        self._processData()

    def _processData(self):
        if len(self.data) < BASE_HEADER.size + 1:
            return
        x, y = BASE_HEADER.unpack_from(self.data)
        size = (x << 16) + y
        if len(self.data) < size + BASE_HEADER.size:
            return
        pkt = SMBPacket(
            data=self.data[BASE_HEADER.size : BASE_HEADER.size + size], proto=self
        )
        self.packetReceived(pkt)
        self.data = self.data[BASE_HEADER.size + size :]
        self._processData()

    def sendPacket(self, data):
        """
        send data with 4 byte header

        @param data: packet to send
        @type data: L{bytes}
        """
        size = len(data)
        assert size < 0xFFFFFF
        x = (size & 0xFF0000) >> 16
        y = size & 0xFFFF
        self.transport.write(BASE_HEADER.pack(x, y) + data)
