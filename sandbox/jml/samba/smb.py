import socket, struct, os
from twisted.internet import protocol, defer
from smbconstants import *
import nmb

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

try:
    import crypt
except ImportError:
    crypt = None



class SharedDevice:
    """Contains information about a SMB shared device/service
    """

    def __init__(self, name, type, comment):
        self.name = name
        self.type = type
        self.comment = comment

    def __repr__(self):
        return ('<SharedDevice instance: name=%s type=%s comment=%s>' %
                (self.name, str(self.type), self.comment))


def smbTimeToEpoch(self, t):
    """Converts the given SMB time to seconds since the UNIX epoch.
    """
    x = t >> 32
    y = t & 0xffffffffL
    geoCalOffset = 11644473600.0
    # = 369.0 * 365.25 * 24 * 60 * 60 - (3.0 * 24 * 60 * 60 + 6.0 * 60 * 60)
    return ((x * 4.0 * (1 << 30) + (y & 0xfff00000L)) * 1.0e-7 - geoCalOffset)

def join(server, *path):
    return '\\\\' + server + '\\' + '\\'.join(path)

class SharedFile:
    """Contains information about the shared file/directory
    """

    def __init__(self, ctime, atime, mtime, filesize, allocsize, attribs,
                 shortname, longname):
        self.ctime = ctime
        self.atime = atime
        self.mtime = mtime
        self.filesize = filesize
        self.allocsize = allocsize
        self.attribs = attribs
        try:
            self.shortName = shortname[:string.index(shortname, '\0')]
        except ValueError:
            self.shortName = shortname
        try:
            self.longName = longname[:string.index(longname, '\0')]
        except ValueError:
            self.longName = longname

    def _checkAttribs(self, flag):
        return self.attribs & flag

    def isArchive(self):
        return self._checkAttribs(ATTR_ARCHIVE)
    
    def isCompressed(self):
        return self._checkAttribs(ATTR_COMPRESSED)

    def isNormal(self):
        return self._checkAttribs(ATTR_NORMAL)

    def isHidden(self):
        return self._checkAttribs(ATTR_HIDDEN)

    def isReadOnly(self):
        return self._checkAttribs(ATTR_READONLY)
    def isTemporary(self):
        return self._checkAttribs(ATTR_TEMPORARY)

    def isDirectory(self):
        return self._checkAttribs(ATTR_DIRECTORY)

    def isSystem(self):
        return self._checkAttribs(ATTR_SYSTEM)

    def __repr__(self):
        return '<SharedFile instance: shortname="' + self.__shortname + '", longname="' + self.__longname + '", filesize=' + str(self.__filesize) + '>'


class SMBMachine:
    """Contains information about an SMB machine.
    """

    def __init__(self, name, type, comment):
        self.name = name
        self.type = type
        self.comment = comment

    def __repr__(self):
        return '<SMBMachine instance: nbname="' + self.__nbname + '", type=' + hex(self.__type) + ', comment="' + self.__comment + '">'


class SMB(nmb.NetBIOSSession):
    # SMB Command Codes
    CREATE_DIR = 0x00
    DELETE_DIR = 0x01
    CLOSE = 0x04
    DELETE = 0x06
    RENAME = 0x07
    CHECK_DIR = 0x10
    READ_RAW = 0x1a
    WRITE_RAW = 0x1d
    TRANSACTION = 0x25
    TRANSACTION2 = 0x32
    OPEN_ANDX = 0x2d
    READ_ANDX = 0x2e
    WRITE_ANDX = 0x2f
    TREE_DISCONNECT = 0x71
    NEGOTIATE = 0x72
    SESSION_SETUP_ANDX = 0x73
    LOGOFF = 0x74
    TREE_CONNECT_ANDX = 0x75
    
    # Security Share Mode
    SECURITY_SHARE_MASK = 0x01
    SECURITY_SHARE_SHARE = 0x00
    SECURITY_SHARE_USER = 0x01
    
    # Security Auth Mode
    SECURITY_AUTH_MASK = 0x02
    SECURITY_AUTH_ENCRYPTED = 0x02
    SECURITY_AUTH_PLAINTEXT = 0x00

    # Raw Mode Mask (Good for dialect up to and including LANMAN2.1)
    RAW_READ_MASK = 0x01
    RAW_WRITE_MASK = 0x02

    # Capabilities Mask (Good for dialect NT LM 0.12)
    CAP_RAW_MODE = 0x0001
    CAP_MPX_MODE = 0x0002
    CAP_UNICODE = 0x0004
    CAP_LARGE_FILES = 0x0008
    CAP_EXTENDED_SECURITY = 0x80000000

    # Flags1 Mask
    FLAGS1_PATHCASELESS = 0x08

    # Flags2 Mask
    FLAGS2_LONG_FILENAME = 0x0001
    FLAGS2_UNICODE = 0x8000

    def __init__(self, localName, remoteName, remoteType):
        self.commands = {
            SMB.CREATE_DIR: self.cmd_createDir,
            SMB.DELETE_DIR: self.cmd_deleteDir,
            SMB.CLOSE: self.cmd_close,
            SMB.DELETE: self.cmd_delete,
            SMB.RENAME: self.cmd_rename,
            SMB.CHECK_DIR: self.cmd_checkDir,
            SMB.READ_RAW: self.cmd_readRaw,
            SMB.WRITE_RAW: self.cmd_writeRaw,
            SMB.TRANSACTION: self.cmd_transaction,
            SMB.TRANSACTION2: self.cmd_transaction2,
            SMB.OPEN_ANDX: self.cmd_openAndX,
            SMB.READ_ANDX: self.cmd_readAndX,
            SMB.WRITE_ANDX: self.cmd_writeAndX,
            SMB.TREE_DISCONNECT: self.cmd_treeDisconnect,
            SMB.NEGOTIATE: self.cmd_negotiate,
            SMB.SESSION_SETUP_ANDX: self.cmd_sessionSetupAndX,
            SMB.LOGOFF: self.cmd_logoff,
            SMB.TREE_CONNECT_ANDX: self.cmd_treeConnectAndX
            }
        
        nmb.NetBIOSSession.__init__(self)
        self.localName = localName
        self.remoteName = remoteName
        self.remoteType = remoteType
        self.transactions = {}
        self.transactions2 = {}
        self.userID = 0

    def sendPacket(self, cmd, param='', data='', status=0, flags=0, flags2=0,
                   tid=0, mid=0):
        wordCount = len(param)
        assert wordCount & 0x1 == 0
        nmb.NetBIOSSession.sendPacket(self,
            struct.pack('<4sBLBH12sHHHHB', '\xffSMB', cmd, status, flags,
                        flags2, '\0' * 12, tid, os.getpid(), self.userID, mid,
                        wordCount / 2)
            + param + struct.pack('<H', len(data)) + data)

    def _decodeSMB(self, data):
        (_, cmd, err_class, _, err_code, flags1, flags2, _, tid, pid, uid, mid,
         wcount) = struct.unpack('<4sBBBHBH12sHHHHB', data[:33])
        param_end = 33 + wcount * 2
        return (cmd, err_class, err_code, flags1, flags2, tid, uid, mid,
                data[33:param_end], data[param_end + 2:])

    def gotPacket(self, data):
        self._gotSMBPacket(*(self._decodeSMB(data)))

    def _gotSMBPacket(self, cmd, errClass, errCode, flags1, flags2, tid, uid,
                      mid, params, data):
        cmd = self.commands[cmd]
        print cmd.__name__
        if errClass == 0x00 and errCode == 0x00:
            cmd(flags1, flags2, tid, uid, mid, params, data)
        else:
            raise ValueError, "Error"

    def connectionMade(self):
        d = self.establishSession(self.localName, self.remoteName,
                                  self.remoteType)
        d.addCallback(self._negotiateSMBSession)
        d.addErrback(self.sessionFailed)

    def _negotiateSMBSession(self, data):
        self.sendPacket(self.NEGOTIATE, data='\x02NT LM 0.12\x00')

    def cmd_negotiate(self, flags1, flags2, tid, uid, mid, params, data):
        selDialect = struct.unpack('<H', params[:2])
        if selDialect == 0xffff:
            raise UnsupportedFeature, "Remote server does not know NT LM 0.12. Please file a request for backward compatibility support."
                        
        # NT LM 0.12 dialect selected
        (auth, self._maxmpx, self._maxvc, self._maxTransmitSize,
         self._maxRawSize, self._sessionKey, capability, _,
         keyLength) = struct.unpack('<BHHllll10sB', params[2:34])

        if capability & SMB.CAP_EXTENDED_SECURITY:
            raise UnsupportedFeature, "This version of pysmb does not support extended security validation. Please file a request for it."

        self._authMode = auth & SMB.SECURITY_AUTH_MASK
        self._shareMode = auth & SMB.SECURITY_SHARE_MASK
        rawMode = capability & SMB.CAP_RAW_MODE
        self._canReadRaw = rawMode
        self._canWriteRaw = rawMode
        self._isPathCaseless = flags1 & SMB.FLAGS1_PATHCASELESS

        if keyLength > 0 and len(data) >= keyLength:
            self._encKey = data[:keyLength]
        else:
            self._encKey = ''

        if self._shareMode == SMB.SECURITY_SHARE_SHARE:
            self.login('', '')
        else:
            self.sessionEstablished()

    def sessionFailed(self, reason):
        print 'Session establishment failed'
        print reason
        self.transport.loseConnection()

    def sessionEstablished(self):
        raise NotImplementedError, "User needs to implement this"

    def login(self, username, password, domain=''):
        if self._encKey and crypt:
            password = crypt.hash(password, self._encKey)
        params = struct.pack('<ccHHHHLHHLL', '\xff', '\0', 0, 65535, 2,
                             os.getpid(), self._sessionKey, len(password), 0, 0,
                             SMB.CAP_RAW_MODE)
        datas = "%s%s\0%s\0%s\0%s\0" % (password, username, domain,
                                        os.name, 'pysmb')
        self.sendPacket(SMB.SESSION_SETUP_ANDX, param=params, data=datas)

    def cmd_sessionSetupAndX(self, flags1, flags2, tid, uid, mid, params, d):
        self.userID = uid
        securityBlobLength = struct.unpack('<H', params[4:6])[0]
        print 'sessionSetupAndX'
        if flags2 & SMB.FLAGS2_UNICODE:
            offset = securityBlobLength
            if offset & 0x01:
                offset += 1
                
            # Skip server OS
            print 'skipping server os'
            end = offset
            while ord(d[end]) or ord(d[end + 1]):
                end += 2
            try:
                self._serverOS = unicode(d[offset:end], 'utf_16_le')
            except NameError:
                self._serverOS = d[offset:end]
            end += 2
            offset = end

            # Skip server lanman
            print 'skipping server lanman'
            while ord(d[end]) or ord(d[end + 1]):
                end += 2
            try:
                self._serverLanMan = unicode(d[offset:end], 'utf_16_le')
            except NameError:
                self._serverLanMan = d[offset:end]
            end += 2
            offset = end

            print 'getting server domain'
            while ord(d[end]) or ord(d[end + 1]):
                end += 2
            try:
                self._serverDomain = unicode(d[offset:end], 'utf_16_le')
            except NameError:
                self._serverDomain = d[offset:end]
        else:
            print 'garr'
            idx1 = d.find('\0', securityBlobLength)
            if idx1 != -1:
                self._serverOS = d[securityBlobLength:idx1]
                idx2 = d.find('\0', idx1 + 1)
                if idx2 != -1:
                    self._serverLanMan = d[idx1 + 1:idx2]
                    idx3 = d.find('\0', idx2 + 1)
                    if idx3 != -1:
                        self._serverDomain = d[idx2 + 1:idx3]
            print 'garr'
        print 'calling session'
        self.sessionEstablished()
        print 'foo'

    def _connectTree(self, path, service, password=None):
        if password:
            if self._encKey and crypt:
                password = hash(password)
        else:
            password = '\0'

        self.sendPacket(SMB.TREE_CONNECT_ANDX,
                        struct.pack('<BBHHH', 0x0ff, 0, 0, 0,
                                    len(password)),
                        password + path.upper() + '\0' +
                        service + '\0')
        self._connectTreeD = defer.Deferred()
        return self._connectTreeD

    def cmd_treeConnectAndX(self, flags1, flags2, tid, uid, mid, params, d):
        self._connectTreeD.callback(tid)
        self._connectTreeD = None

    def transact(self, command, path, service, password, setup, name, param,
                 data):
        d = self._connectTree(path, service, password)
        d.addCallback(transactor, command, setup, name, param, data)
        return d

    def _transact(self, tid, command, setup, name, param, data):
        d = defer.Deferred()
        self.transactions[tid] = command, d
        assert len(setup) & 0x01 == 0

        paramOffset = len(name) + len(setup) + 63
        dataOffset = paramOffset + len(param)
        
        self.sendPacket(SMB.TRANSACTION, 
                        struct.pack('<HHHHBBHLHHHHHBB', len(param), len(data),
                                    1024, 65504, 0, 0, 0, 0, 0, len(param),
                                    paramOffset, len(data), dataOffset,
                                    len(setup) / 2, 0) + setup,
                        name + param + data,
                        0, int(self._isPathCaseless),
                        SMB.FLAGS2_LONG_FILENAME, tid, 0)
        return d

    def _decodeTrans(self, params, data):
        (totalParamCount, totalDataCount, _, paramCount, paramOffset, paramds,
         dataCount, dataOffset, datads, setupCount) \
         = struct.unpack('<HHHHHHHHHB', params[:19])

        hasMore = ((paramCount + paramds < totalParamCount) or
                   (dataCount + datads < totalDataCount))
        paramOffset = paramOffset - 55 - setupCount * 2
        dataOffset = dataOffset - 55 - setupCount * 2
        return (hasMore, params[20:20 + setupCount * 2],
                data[paramOffset:paramOffset + paramCount],
                data[dataOffset:dataOffset + dataCount])


    def cmd_transaction(self, flags1, flags2, tid, uid, mid, params, d):
        cmd, deferred = self.transactions[tid]
        ret = cmd(flags1, flags2, tid, uid, mid,
                  *(self._decodeTrans(params, d)))
        if ret is not None:
            deferred.callback(ret)

    def listShares(self):
        d = self.transact(self._listShares, join(self.remoteName, 'IPC$'),
                          SERVICE_ANY, None, '', '\\PIPE\\LANMAN\\0',
                          '\x00\x00WrLeh\0B13BWz\0\x01\x00\xe0\xff', '')
        return d

    def _listShares(self, flags1, flags2, tid, uid, mid, hasMore,
                    params, transParam, transData, buf=StringIO()):
        if not buf.getvalue():
            numEntries = struct.unpack('<H', transParam[4:6])[0]
        
        buf.write(transData)

        if hasMore:
            return None
        
        shareData = buf.getvalue()
        offset = 0
        shareList = []
        for i in range(numEntries):
            name = shareData[offset:shareData.find('\0', offset)]
            type, commentOffset = struct.unpack('<HH', shareData[offset + 14:offset + 18])
            comment = shareData[commentOffset:transData.find('\0', commentOffset)]
            offset += 20
            shareList.append(SharedDevice(name, type, comment))
        buf = StringIO()
        return shareList

    def cmd_createDir(self, flags1, flags2, tid, uid, mid, params, data):
        raise NotImplementedError
    def cmd_deleteDir(self, flags1, flags2, tid, uid, mid, params, data):
        raise NotImplementedError
    def cmd_close(self, flags1, flags2, tid, uid, mid, params, data): 
        raise NotImplementedError
    def cmd_delete(self, flags1, flags2, tid, uid, mid, params, data): 
        raise NotImplementedError
    def cmd_rename(self, flags1, flags2, tid, uid, mid, params, data): 
        raise NotImplementedError
    def cmd_checkDir(self, flags1, flags2, tid, uid, mid, params, data): 
        raise NotImplementedError
    def cmd_readRaw(self, flags1, flags2, tid, uid, mid, params, data): 
        raise NotImplementedError
    def cmd_writeRaw(self, flags1, flags2, tid, uid, mid, params, data): 
        raise NotImplementedError
    def cmd_transaction2(self, flags1, flags2, tid, uid, mid, params, data): 
        raise NotImplementedError
    def cmd_readAndX(self, flags1, flags2, tid, uid, mid, params, data): 
        raise NotImplementedError
    def cmd_writeAndX(self, flags1, flags2, tid, uid, mid, params, data): 
        raise NotImplementedError
    def cmd_treeDisconnect(self, flags1, flags2, tid, uid, mid, params, data): 
        raise NotImplementedError
    def cmd_logoff(self, flags1, flags2, tid, uid, mid, params, data): 
        raise NotImplementedError
    def cmd_openAndX(self, flags1, flags2, tid, uid, mid, params, data):
        raise NotImplementedError


class SMBFactory(protocol.ClientFactory):
    protocol = SMB
    
    def __init__(self, remoteName, remoteType=nmb.TYPE_SERVER, localName=None):
        if localName is None:
            localName = socket.gethostname().split('.')[0]
        self.localName = localName
        self.remoteName = remoteName
        self.remoteType = remoteType


    def buildProtocol(self, addr):
        p = self.protocol(self.localName, self.remoteName, self.remoteType)
        p.factory = self
        return p

