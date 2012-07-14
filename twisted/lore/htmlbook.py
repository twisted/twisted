# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.python.compat import execfile


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
            execfile(filename, globals())

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
