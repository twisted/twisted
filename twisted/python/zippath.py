# -*- test-case-name: twisted.test.test_paths.ZipFilePathTestCase -*-

"""

This module contains partial re-implementations of FilePath, pending some
specification of formal interfaces it is a duck-typing attempt to emulate them
for certain restricted uses.

"""

__metaclass__ = type

from twisted.python.zipstream import ChunkingZipFile

from twisted.python.filepath import FilePath, _PathHelper

# using FilePath here exclusively rather than os to make sure that we don't do
# anything OS-path-specific here.

class ZipPath(_PathHelper):
    def __init__(self, archive, pathInArchive):
        self.archive = archive
        self.pathInArchive = pathInArchive
        # *should* this be OS-specific?
        self.path = '/'.join([archive.zipfile.filename, self.pathInArchive])

    def __cmp__(self, other):
        if not isinstance(other, ZipPath):
            return NotImplemented
        return cmp((self.archive, self.pathInArchive),
                   (other.archive, other.pathInArchive))

    def __repr__(self):
        return 'ZipPath(%r)' % (self.path,)

    def parent(self):
        splitup = self.pathInArchive.split('/')
        if len(splitup) == 1:
            return self.archive
        return ZipPath(self.archive, '/'.join(splitup[:-1]))

    def child(self, path):
        return ZipPath(self.archive, '/'.join([self.pathInArchive, path]))

    def sibling(self, path):
        return self.parent().child(path)

    # preauthChild = child

    def exists(self):
        return self.isdir() or self.isfile()

    def isdir(self):
        return self.pathInArchive in self.archive.childmap

    def isfile(self):
        return self.pathInArchive in self.archive.zipfile.NameToInfo

    def islink(self):
        return False

    def listdir(self):
        return self.archive.childmap[self.pathInArchive].keys()

    def splitext(self):
        # ugh, terrible API, these paths are unusable; but the extension is
        # what we're after 99% of the time
        n = self.path.rfind('.')
        return self.path[:n], self.path[n:]

    def basename(self):
        return self.pathInArchive.split("/")[-1]

    def dirname(self):
        return '/'.join(self.pathInArchive.split("/")[:-1])

    def open(self):
        return self.archive.zipfile.readfile(self.pathInArchive)

    def restat(self):
        pass


class ZipArchive(ZipPath):
    archive = property(lambda self: self)
    def __init__(self, archivePathname):
        self.zipfile = ChunkingZipFile(archivePathname)
        self.path = archivePathname
        self.pathInArchive = ''
        # zipfile is already wasting O(N) memory on cached ZipInfo instances,
        # so there's no sense in trying to do this lazily or intelligently
        self.childmap = {}      # map parent: list of children

        for name in self.zipfile.namelist():
            name = name.split('/')
            for x in range(len(name)):
                child = name[-x]
                parent = '/'.join(name[:-x])
                if parent not in self.childmap:
                    self.childmap[parent] = {}
                self.childmap[parent][child] = 1
            parent = ''

    def child(self, path):
        """
        Create a ZipPath pointing at a path within the archive.
        """
        return ZipPath(self, path)

    def exists(self):
        return FilePath(self.zipfile.filename).exists()
