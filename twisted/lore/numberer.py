# Twisted, the Framework of Your Internet
# Copyright (C) 2004 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

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
