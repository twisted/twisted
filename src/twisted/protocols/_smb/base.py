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
    """SMB specific errors
    """
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



SMB_METADATA = '__smb_metadata'



def byte(default=0):
    """an 8-bit unsigned integer

    wraps L{attr.ib} with appropriate metadata for use with L{pack} and
    L{unpack}
    """
    return attr.ib(default=default, type=int, metadata={SMB_METADATA: "B"})



def short(default=0):
    """a 16-bit unsigned integer"""
    return attr.ib(default=default, type=int, metadata={SMB_METADATA: "H"})



def int32(default=0):
    """a 32-bit unsigned integer"""
    return attr.ib(default=default, type=int, metadata={SMB_METADATA: "I"})



def long(default=0):
    """an 64-bit unsigned integer"""
    return attr.ib(default=default, type=int, metadata={SMB_METADATA: "Q"})



def single(default=0.0):
    """a 32-bit float"""
    return attr.ib(default=default, type=float, metadata={SMB_METADATA: "f"})



def double(default=0.0):
    """a 64-bit float"""
    return attr.ib(default=default, type=float, metadata={SMB_METADATA: "d"})



def octets(length=None, default=None):
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
        default = b'\0' * length
    return attr.ib(default=default,
                   type=bytes,
                   metadata={SMB_METADATA: str(length) + "s"})



NULL_UUID = uuid_mod.UUID("00000000-0000-0000-0000-000000000000")
NEW_UUID = attr.Factory(uuid_mod.uuid4)



def uuid(default=NULL_UUID):
    """a universial unique ID"""
    default = _conv_uuid(default)
    return attr.ib(default=default,
                   metadata={SMB_METADATA: "16s"},
                   type=uuid_mod.UUID,
                   converter=_conv_uuid)



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
    args = tuple(_conv_arg(obj, i) for i in attr.fields(type(obj)))
    return strct.pack(*args)



def _conv_arg(obj, attrib):
    val = getattr(obj, attrib.name)
    if type(val) is uuid_mod.UUID:
        val = val.bytes_le
    return val



def unpack(cls, data, offset=0, remainder=0):
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
                      - C{0} ignore it
                      - C{1} throw a L{SMBError}
                      - C{2} return offset into data
                        where remainder begins as second item of tuple
                      - C{3} return remaining data as second item of tuple
    @type remainder: L{int}

    @param offset: offset into data to begin from
    @type offset: L{int}

    @return: an instance of C{cls}, or a 2-tuple, first item the former,
             second as determined by C{remainder}
    """
    strct = _get_struct(cls)
    if remainder == 1 and strct.size + offset < len(data):
        raise SMBError("unexpected remaining data")
    ret = strct.unpack_from(data, offset=offset)
    fields = attr.fields(cls)
    assert len(fields) == len(ret)
    kwargs = {}
    for i in range(len(ret)):
        val = ret[i]
        if fields[i].type is uuid_mod.UUID:
            val = uuid_mod.UUID(bytes_le=val)
        kwargs[fields[i].name] = val
    obj = cls(**kwargs)
    if remainder <= 1:
        return obj
    elif remainder == 2:
        return (obj, offset + strct.size)
    else:
        return (obj, data[offset + strct.size:])



def _get_struct(cls):
    try:
        # we use classes to hold cache of Structs as precompiling is more
        # efficient
        strct = cls._struct
    except AttributeError:
        strct = struct.Struct("<" + "".join(i.metadata[SMB_METADATA]
                                            for i in attr.fields(cls)))
        cls._struct = strct
    return strct



class GeneralStruct:
    """
    a more ergonomic struct.unpack/pack. an object that represents an ordered
    binary structure and field names..
    field names are acceessible as attributes.
    don't use directly, subclass through L{base.nstruct}
    """
    def __init__(self, data=None):
        """
        @param data: binary data sent to C{pack}
        @type data: L{bytes}
        """
        self.buffer = b''
        self._values = {}
        if data:
            self.unpack(data)

    def __setattr__(self, name, val):
        if name in self._fields_names:
            self._values[name] = val
        else:
            object.__setattr__(self, name, val)

    def zero(self, field):
        """
        get logical zero/null value for a field
        """
        n = self._fields_names.index(field)
        t = self._types[n]
        if t.endswith("s"):
            return b"\0" * int(t[0:-1])
        else:
            return 0

    def __getattr__(self, name):
        if name in self._fields_names:
            return self._values.get(name, self.zero(name))
        else:
            raise AttributeError(name)

    def pack(self):
        """
        Pack data according to the pattern

        @rtype: L{bytes}
        """
        p = [self._values.get(n, self.zero(n)) for n in self._fields_names]
        return struct.pack(self._pattern, *p) + self.buffer

    def unpack(self, data):
        """
        unpack data according to the pattern
        exceas data goes in buffer

        @param data: the data
        @type data: L{bytes}
        """
        ret = struct.unpack(self._pattern, data[:self._size])
        for i in range(len(ret)):
            self._values[self._fields_names[i]] = ret[i]
        self.buffer = data[self._size:]

    def clear(self):
        """
        clear internal fields
        """
        self._values = {}
        self.buffer = b''

    def __len__(self):
        return self._size

    def __bytes__(self):
        return self.pack()



def nstruct(fields):
    """
    dynamically subclass GeneralStruct with a speeific binary structure

    @param fields: space-separated list field:type.
    Type is a single char as used in L{struct.pack}
    (but only use s and numeric types)
    @type fields: L{str}
    """
    d = {}
    d['_fields_names'] = []
    d['_types'] = []
    for f in fields.split():
        f = f.split(":")
        d['_fields_names'].append(f[0])
        d['_types'].append(f[1])
    d['_pattern'] = "<" + "".join(d['_types'])
    d['_size'] = struct.calcsize(d['_pattern'])
    return type(d['_pattern'], (GeneralStruct, ), d)



_leint = struct.Struct("<I")



def int32key(d, val):
    """
    generate a new random key for a dictionary
    @param d: dictionary with 32-bit int keys
    @type d: L{dict}
    @param val: new dictionary value
    @rtype: L{int}
    """
    assert len(d) < 0xc0000000  # otherwiae dict so big hard to find keys
    n = 0
    while n == 0 or n in d:
        [n] = _leint.unpack(secureRandom(_leint.size, True))
    d[n] = val
    return n



BASE_HEADER = struct.Struct("!xBH")



class SMBPacketReceiver(protocol.Protocol):
    """
    A L{SMBPacketReceiver} is a wire protocol parser for the SMB framing
    mechanism, which consist of a 4-byte header: single null
    and a 24-bit length field.
    """
    def __init__(self):
        self.data = b''

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
        self.packetReceived(self.data[BASE_HEADER.size:BASE_HEADER.size +
                                      size])
        self.data = self.data[BASE_HEADER.size + size:]
        self._processData()

    def sendPacket(self, data):
        """
        send data with 4 byte header

        @param dara: packet to send
        @type data: L{bytes}
        """
        size = len(data)
        assert size < 0xffffff
        x = (size & 0xff0000) >> 16
        y = size & 0xffff
        self.transport.write(BASE_HEADER.pack(x, y) + data)

    def packetReceived(self, packet):
        """
        called for each complete packet received over network
        override in descendants

        @param packet: raw packet data
        @type packet: L{bytes}
        """
