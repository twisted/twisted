##Beginnings of an implementation of the NMB protocols.
#
##Features support for name resolution, node status and NetBIOS session
##(establishment and use).
#
##Everything is written (and tested) from a client POV. However the NetBIOS
##session stuff is reasonably symmetric.
#
##Ported from pysmb, http://miketeo.net/projects/pysmb/
#
##@author Jonathan Lange <jml@mumak.net>

import re, os, random, string, struct
from twisted.internet import protocol, defer

"""Default port for NetBIOS name service."""
NETBIOS_NS_PORT = 137

"""Default port for NetBIOS session service."""
NETBIOS_SESSION_PORT = 139

# Owner Node Type Constants
NODE_B = 0x00
NODE_P = 0x01
NODE_M = 0x10
NODE_RESERVED = 0x11

# Name Type Constants
TYPE_UNKNOWN = 0x01
TYPE_WORKSTATION = 0x00
TYPE_CLIENT = 0x03
TYPE_SERVER = 0x20
TYPE_DOMAIN_MASTER = 0x1B
TYPE_MASTER_BROWSER = 0x1D
TYPE_BROWSER = 0x1E


class NetBIOSException(Exception):
    def __init__(self, errorCode):
        msg = '%s (%d)' % (self.errors.get(errorCode, 'Unknown error.'),
                           errorCode)
        Exception.__init__(self, msg)


class NetBIOSQueryException(NetBIOSException):
    errors = {
        0x01: 'Request format error. Please file a bug report.',
        0x02: 'Internal server error',
        0x03: 'Name does not exist',
        0x04: 'Unsupported request',
        0x05: 'Request refused'
        }


class NetBIOSSessionException(NetBIOSException):
    errors = { 0x80: 'Not listening on called name',
               0x81: 'Not listening for calling name',
               0x82: 'Called name not present',
               0x83: 'Insufficient resources',
               0x8f: 'Unspecified error'
               }


class NBHostEntry:
    def __init__(self, name, nameType, ip):
        self.name = name
        self.nameType = nameType
        self.ip = ip

    def __repr__(self):
        return '<NBHostEntry instance: NBname="' + self.name + '", IP="' + self.ip + '">'


class NBNodeEntry:
    NAME_TYPES = { TYPE_UNKNOWN: 'Unknown',
                   TYPE_WORKSTATION: 'Workstation',
                   TYPE_CLIENT: 'Client',
                   TYPE_SERVER: 'Server',
                   TYPE_MASTER_BROWSER: 'Master Browser',
                   TYPE_BROWSER: 'Browser Server',
                   TYPE_DOMAIN_MASTER: 'Domain Master' }
    
    def __init__(self, name, nameType, isGroup, nodeType, deleting,
                 isConflict, isActive, isPermanent):
        self.name = name
        self.nameType = nameType
        self.isGroup = isGroup
        self.nodeType = nodeType
        self.deleting = deleting
        self.isConflict = isConflict
        self.isActive = isActive
        self.isPermanent = isPermanent

    def __repr__(self):
        s = '<NBNodeEntry instance: NBname=%r NameType=%r %s>'
        status = ''
        if self.isActive:
            status += ' ACTIVE'
        if self.isGroup:
            status += ' GROUP'
        if self.isConflict:
            status += ' CONFLICT'
        if self.deleting:
            status += ' DELETING'
        return s % (self.name, self.NAME_TYPES[self.nameType], status)


def encodeName(name, type, scope):
    """Perform first and second level encoding of name as specified in RFC 1001
    (Section 4).
    """

    def _doFirstLevelEncoding(m):
        """Internal method for use in encode_name()
        """
        s = ord(m.group(0))
        return string.uppercase[s >> 4] + string.uppercase[s & 0x0f]

    if name == '*':
        name = name + '\0' * 15
    elif len(name) > 15:
        name = name[:15] + chr(type)
    else:
        name = string.ljust(name, 15) + chr(type)
        
    encoded_name = chr(len(name) * 2) + re.sub('.', _doFirstLevelEncoding, name)
    if scope:
        encoded_scope = ''
        for s in string.split(scope, '.'):
            encoded_scope = encoded_scope + chr(len(s)) + s
        return encoded_name + encoded_scope + '\0'
    else:
        return encoded_name + '\0'


def decodeName(name):
    def _doFirstLevelDecoding(m):
        s = m.group(0)
        return chr(((ord(s[0]) - ord('A')) << 4) | (ord(s[1]) - ord('A')))

    name_length = ord(name[0])
    assert name_length == 32

    decoded_name = re.sub('..', _doFirstLevelDecoding, name[1:33])
    if name[33] == '\0':
        return 34, decoded_name, ''
    else:
        decoded_domain = ''
        offset = 34
        while 1:
            domain_length = ord(name[offset])
            if domain_length == 0:
                break
            decoded_domain = '.' + name[offset:offset + domain_length]
            offset = offset + domain_length
        return offset + 1, decoded_name, decoded_domain


class NetBIOS(protocol.DatagramProtocol):
    def __init__(self):
        self.transactions = {}
        self.handlers = {}

    def beginTransaction(self):
        trxID = random.randint(0, 32000)
        while trxID in self.transactions:
            trxID = random.randint(0, 32000)
        self.transactions[trxID] = defer.Deferred()
        return trxID

    def endTransaction(self, trxID):
        del self.transactions[trxID]
        del self.handlers[trxID]

    def getTransaction(self, trxID):
        return self.transactions[trxID]

    def datagramReceived(self, data, (destServer, destPort)):
        trxID = struct.unpack('>H', data[:2])[0]
        if trxID not in self.transactions:
            raise NetBIOSQueryException()
        d = self.transactions[trxID]
        self._checkReturnCode(data)
        ret = self.handlers[trxID](trxID, data)
        d.callback(ret)

    def _checkReturnCode(self, data):
        returnCode = ord(data[3]) & 0x0f
        if returnCode:
            raise NetBIOSQueryException(returnCode)

    def _constructRequest(self, requestFlag, trxID, name, type, scope,
                          broadcast):
        if broadcast:
            broadcastFlag = 0x0110
        else:
            broadcastFlag = 0x0100
        request = (struct.pack('>HHHHHH', trxID, broadcastFlag, 0x01, 0x00,
                               0x00, 0x00)
                   + encodeName(name.upper(), type, scope)
                   + struct.pack('>HH', requestFlag, 0x01))
        return request

    def lookupName(self, name, destServer=None, destPort=137, broadcast=False,
                   type=TYPE_WORKSTATION, scope=None):
        trxID = self.beginTransaction()
        request = self._constructRequest(0x20, trxID, name, type, scope,
                                         broadcast)
        self.handlers[trxID] = self.gotData_lookup
        self.transport.write(request, (destServer, destPort))
        return self.transactions[trxID]

    def gotData_lookup(self, trxID, data):
        addresses = []
        qnLength, qnName, qnScope = decodeName(data[12:])
        offset = 20 + qnLength
        numRecords = (struct.unpack('>H', data[offset:offset + 2])[0] - 2) / 4
        offset = offset + 4
        for i in range(numRecords):
            import socket
            netbiosName = qnName[:-1].rstrip() + qnScope
            nameType = ord(qnName[-1])
            ip = socket.inet_ntoa(data[58 + i * 4:62 + i * 4])
            entry = NBHostEntry(netbiosName, nameType, ip)
            addresses.append(entry)
            offset = offset + 4
        self.endTransaction(trxID)
        return addresses

    def getNodeStatus(self, name, destServer, destPort=137, broadcast=False,
                      type=TYPE_WORKSTATION, scope=None):
        """Returns a list of NBNodeEntry instances containing node status
        information for nbname. If destaddr contains an IP address, then this
        will become an unicast query on the destaddr.
        
        Raises NetBIOSError for other errors
        """
        trxID = self.beginTransaction()
        request = self._constructRequest(0x21, trxID, name, type, scope,
                                         broadcast)
        self.transport.write(request, (destServer, destPort))
        self.handlers[trxID] = self.gotData_nodeStatus
        return self.transactions[trxID]

    def gotData_nodeStatus(self, trxID, data):
        nodes = [ ]
        numNames = ord(data[56])
        for i in range(numNames):
            recStart = 57 + i * 18
            name = re.sub(chr(0x20) + '*$', '', data[recStart:recStart + 15])
            type, flags = struct.unpack('>BH',
                                        data[recStart + 15: recStart + 18])
            nodes.append(NBNodeEntry(name, type, flags & 0x8000, flags & 0x6000,
                                     flags & 0x1000, flags & 0x0800,
                                     flags & 0x0400, flags & 0x0200))
                             
        return nodes


def lookup(*args, **kwargs):
    from twisted.internet import reactor
    nb = NetBIOS()
    reactor.listenUDP(0, nb)
    return nb.lookupName(*args, **kwargs)


def queryNode(*args, **kwargs):
    from twisted.internet import reactor
    nb = NetBIOS()
    reactor.listenUDP(0, nb)
    return nb.getNodeStatus(*args, **kwargs)


class NetBIOSSession(protocol.Protocol):
    def __init__(self):
        self.established = None

    def establishSession(self, localName, remoteName, remoteType=TYPE_SERVER):
        if self.established:
            raise ValueError, "Session already established"
        
        remoteName = encodeName(remoteName[:15].upper(), remoteType, None)
        localName = encodeName(localName[:15].upper(), TYPE_WORKSTATION, None)

        request = ('\x81\x00'
                   + struct.pack('>H', len(remoteName) + len(localName))
                   + remoteName
                   + localName)
        self.transport.write(request)
        self.d = defer.Deferred()
        return self.d

    def sendPacket(self, data):
        self.transport.write('\x00\x00%s%s' % (struct.pack('>H', len(data)),
                                               data))
    def gotPacket(self, data):
        pass
        
    def dataReceived(self, data):
        type, flags, length = struct.unpack('>ccH', data[:4])
        type, flags = ord(type), ord(flags)
        if flags & 0x01:
            length |= 0x10000
        header, data = data[:4], data[4:]

        if len(data) != length:
            print 'warning, wrong length'
            
        if not self.established:
            if type == 0x83:
                raise NetBIOSSessionException(ord(data[0]))
            elif type == 0x82:
                self.established = True
                self.d.callback(data)
            else:
                return None # probably a keepalive or something
        else:
            if type == 0x00:
                self.gotPacket(data)
            else:
                return None
