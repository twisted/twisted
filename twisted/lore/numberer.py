# -*- test-case-name: twisted.lore.test.test_numberer -*-
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
APIs for assigning numbers to sections of a document.
"""

from twisted.python.versions import Version
from twisted.python.deprecate import deprecated

_unreleasedVersion = Version('Twisted', 8, 0, 0)
_unreleasedDeprecation = deprecated(_unreleasedVersion)

class Numberer(object):
    """
    This class tracks the state of numbering within a particular document and
    assigns numbers in consecutive increasing order, starting from 1.

    @type _filenum: C{int}
    @ivar _filenum: The I{current} file number.  This is one less than the
        value which will be returned by L{getNextFileNumber}.

    @type numberSections: C{bool}
    @ivar numberSections: A flag indicating whether sections should be
        numbered.
    """
    def __init__(self):
        self._filenum = 0
        self.numberSections = False


    def getNextFileNumber(self):
        """
        @rtype: C{int}
        @return: The smallest file number not yet used.
        """
        self._filenum += 1
        return self._filenum


    def getFileNumber(self):
        """
        @rtype: C{int}
        @return: The most recently used file number.
        """
        return self._filenum


    def setFileNumber(self, number):
        """
        Change the current file number.

        @type number: C{int}
        @param number: A value one less than the next file number to allocate.
        """
        self._filenum = number


    def resetFileNumber(self):
        """
        Set the file number back to its initial state.
        """
        self._filenum = 0


    def reset(self):
        """
        Set everything back to its initial state.
        """
        self.resetFileNumber()
        self.numberSections = False


filenum = 0
numberSections = False

def reset():
    resetFilenum()
    setNumberSections(False)
reset = _unreleasedDeprecation(reset)

def resetFilenum():
    setFilenum(0)

def setFilenum(arg):
    global filenum
    filenum = arg
setFilenum = _unreleasedDeprecation(setFilenum)

def getFilenum():
    global filenum
    return filenum
getFilenum = _unreleasedDeprecation(getFilenum)

def getNextFilenum():
    global filenum
    filenum += 1
    return filenum
getNextFilenum = _unreleasedDeprecation(getNextFilenum)

def setNumberSections(arg):
    global numberSections
    numberSections = arg
setNumberSections = _unreleasedDeprecation(setNumberSections)

def getNumberSections():
    global numberSections
    return numberSections
getNumberSections = _unreleasedDeprecation(getNumberSections)
