
from smbconstants import *
import nmb

class SharedDevice:
    """Contains information about a SMB shared device/service
    """

    def __init__(self, name, type, comment):
        self.name = name
        self.type = type
        self.comment = comment

    def __repr__(self):
        return '<SharedDevice instance: name=' + self.__name + ', type=' + str(self.__type) + ', comment="' + self.__comment + '">'


def smbTimeToEpoch(self, t):
    """Converts the given SMB time to seconds since the UNIX epoch.
    """
    x = t >> 32
    y = t & 0xffffffffL
    geoCalOffset = 11644473600.0
    # = 369.0 * 365.25 * 24 * 60 * 60 - (3.0 * 24 * 60 * 60 + 6.0 * 60 * 60)
    return ((x * 4.0 * (1 << 30) + (y & 0xfff00000L)) * 1.0e-7 - geoCalOffset)


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

