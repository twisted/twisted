# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


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
