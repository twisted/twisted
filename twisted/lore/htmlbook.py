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

def getNumber(filename):
    return None

def getReference(filename):
    return None

class Book:

    def __init__(self, filename):
        self.chapters = []
        self.indexFilename = None

        global Chapter
        Chapter = self.Chapter
        global getNumber
        getNumber = self.getNumber
        global getReference
        getReference = self.getNumber
        global Index
        Index = self.Index

        if filename:
            execfile(filename)

    def getFiles(self):
        return [c[0] for c in self.chapters]

    def getNumber(self, filename):
        for c in self.chapters:
            if c[0] == filename:
                return c[1]
        return None

    def getIndexFilename(self):
        return self.indexFilename

    def Chapter(self, filename, number):
        self.chapters.append((filename, number))

    def Index(self, filename):
        self.indexFilename = filename

#_book = Book(None)
