# -*- test-case-name: twisted.lore.test.test_lore -*-
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Support for representing collections of documents.
"""

class Book:
    """
    Represents a multi-file book, which may have a whole-book index and table
    of contents.

    A Book has a book file, which is executable Python code that calls the
    C{index()}, C{chapter()}, and C{useForTOC()} methods in this module.  The
    book file is executed when the Book object is instantiated.

    @ivar chapters: A C{list} of two-tuples of strings.  The first element of
        each tuple is a filename, the second is the corresponding chapter
        identifier.

    @ivar indexFilename: The name out of the output file.
    """

    def __init__(self, filename):
        """
        Initialize an empty instance of Book.  As soon as it is initialized,
        its book file (C{filename}) is executed to populate it.

        @type filename: C{str}
        @param filename: the filename of its book file
        """
        self.chapters = []
        self.indexFilename = None
        self.filename = filename

        global _book
        _book = self

        if filename:
            execfile(
                filename,
                {'chapter': self.chapter,
                 'index': self.index,
                 'setIndexTemplateFilename': self.setIndexTemplateFilename})


    def getFiles(self):
        return [c[0] for c in self.chapters]


    def getNumber(self, filename):
        """
        Get the chapter number of the chapter corresponding to C{filename}.

        @type filename: C{str}
        @param filename: the filename of the chapter

        @rtype: C{str}
        @return: the chapter number of the chapter
        """
        for c in self.chapters:
            if c[0] == filename:
                return c[1]
        return None
    getReference = getNumber


    def getIndexFilename(self):
        return self.indexFilename

    _indexTemplate = None
    def getIndexTemplateFilename(self):
        return self._indexTemplate

    def setIndexTemplateFilename(self, filename):
        self._indexTemplate = filename

    def chapter(self, filename, number):
        """
        Add a chapter to this book.

        @type filename: C{str}
        @param filename: The name of the file which contains the markup for the
            chapter to add.

        @type number: C{str}
        @param number: The number of the chapter to add.  For example, "3",
            "IV", or "A".
        """
        self.chapters.append((filename, number))


    def index(self, filename):
        """
        Specify the location of the index output.

        @type filename: C{str}
        @param filename: The name of the file to which the index will be
            written.
        """
        self.indexFilename = filename


    def useForTOC(self, levels):
        """
        Set which levels of header to use in the table of contents.

        @type levels: C{str}
        @param levels: a string containing the levels to include as digits;
          e.g. "234" to include levels H2 through H4
        """
        import tree
        print 'Using these header levels in ToCs: ' + levels
        tree.contentsHeaderLevels = levels


_book = Book(None)

def usingBook():
    """
    Return whether this run of Lore is using a Book file
    @rtype: C{boolean}
    @return: C{True} if and only if this run is using a Book file
    """
    return _book.filename != None
