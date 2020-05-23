# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
# -*- test-case-name: twisted.protocols._smb.tests -*-
"""
base classes for SMB networking
"""

from __future__ import absolute_import, division

import struct

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

def u2nt_time(epoch):
    """
    Convert UNIX epoch time to NT filestamp
    quoting from spec: The FILETIME structure is a 64-bit value 
    that represents the number of 100-nanosecond intervals that
    have elapsed since January 1, 1601, Coordinated Universal Time.
    
    @param epoch: seconds since 1/1/1970
    @type epoch: L{float}
     
    @rtype: L{int}
    """
    return int(epoch*10000000.0)+116444736000000000
    
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
       if data: self.unpack(data)
       
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
            return b"\0"*int(t[0:-1])
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
    return type(d['_pattern'], (GeneralStruct,), d)
       
def int32key(d, val):
    """
    generate a new random key for a dictionary
    @param d: dictionary with 32-bit int keys
    @type d: L{dict}
    @param val: new dictionary value
    @rtype: L{int}
    """
    assert len(d) < 0xc0000000 # otherwiae dict so big hard to find keys
    n, = struct.unpack("<I", secureRandom(4, True))
    while n == 0 or n in d:
        n, = struct.unpack("<I", secureRandom(4, True))
    d[n] = val
    return n
    
class SMBPacketReceiver(protocol.Protocol):
    """
    basic SMB 2.0 packets over TCP have a 4-byte header: null byte 
    and 24-bit length field
    this base class processes these headers
    """
    def __init__(self):
        self.data = b''
        
    def dataReceived(self, data):
        self.data += data
        self._processData()
        
    def _processData(self):
        if len(self.data) < 5:
            return
        x, y = struct.unpack("!xBH", self.data[:4])
        size = (x << 16) + y
        if len(self.data) < size+4:
            return
        self.packetReceived(self.data[4:4+size])
        self.data = self.data[4+size:]
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
        self.transport.write(struct.pack("!BBH", 0, x, y) + data)

    def packetReceived(self, packet):
        """
        called for each complete packet received over network
        override in descendants
         
        @param packet: raw packet data
        @type packet: L{bytes}
        """
        pass
