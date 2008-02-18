# -*- test-case-name: twisted.lore.test.test_numberer -*-
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
APIs for assigning numbers to sections of a document.
"""


class Numberer(object):
    """
    This class tracks the state of numbering within a particular document and
    assigns numbers in consecutive increasing order, starting from 1.

    @type _filenum: C{int}
    @ivar _filenum: The I{current} file number.  This is one less than the
        value which will be returned by L{getNextFileNumber}.
    """
    def __init__(self):
        self._filenum = 0


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
        Set everything back to its initial state.
        """
        self._filenum = 0



def reset():
    resetFilenum()
    setNumberSections(False)

def resetFilenum():
    setFilenum(0)

def setFilenum(arg):
    global filenum
    filenum = arg

def getFilenum():
    global filenum
    return filenum

def getNextFilenum():
    global filenum
    filenum += 1
    return filenum

def setNumberSections(arg):
    global numberSections
    numberSections = arg

def getNumberSections():
    global numberSections
    return numberSections

reset()
