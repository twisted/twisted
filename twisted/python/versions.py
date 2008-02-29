# -*- test-case-name: twisted.python.test.test_versions -*-
# Copyright (c) 2006-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Versions for Python packages.

See L{Version}.
"""

import sys, os

class IncomparableVersions(TypeError):
    """
    Two versions could not be compared.
    """

class Version(object):
    """
    An object that represents a three-part version number.

    If running from an svn checkout, include the revision number in
    the version string.
    """
    def __init__(self, package, major, minor, micro):
        self.package = package
        self.major = major
        self.minor = minor
        self.micro = micro

    def short(self):
        """
        Return a string in canonical short version format,
        <major>.<minor>.<micro>[+rSVNVer].
        """
        s = self.base()
        svnver = self._getSVNVersion()
        if svnver:
            s += '+r' + str(svnver)
        return s

    def base(self):
        """
        Like L{short}, but without the +rSVNVer.
        """
        return '%d.%d.%d' % (self.major,
                             self.minor,
                             self.micro)

    def __repr__(self):
        svnver = self._formatSVNVersion()
        if svnver:
            svnver = '  #' + svnver
        return '%s(%r, %d, %d, %d)%s' % (
            self.__class__.__name__,
            self.package,
            self.major,
            self.minor,
            self.micro,
            svnver)

    def __str__(self):
        return '[%s, version %d.%d.%d%s]' % (
            self.package,
            self.major,
            self.minor,
            self.micro,
            self._formatSVNVersion())

    def __cmp__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        if self.package != other.package:
            raise IncomparableVersions("%r != %r"
                                       % (self.package, other.package))
        return cmp((self.major,
                    self.minor,
                    self.micro),
                   (other.major,
                    other.minor,
                    other.micro))


    def _parseSVNEntries_4(self, entriesFile):
        """
        Given a readable file object which represents a .svn/entries file in
        format version 4, return the revision as a string.  We do this by
        reading first XML element in the document that has a 'revision'
        attribute.
        """
        from xml.dom.minidom import parse
        doc = parse(entriesFile).documentElement
        for node in doc.childNodes:
            if hasattr(node, 'getAttribute'):
                rev = node.getAttribute('revision')
                if rev is not None:
                    return rev.encode('ascii')


    def _parseSVNEntries_8(self, entriesFile):
        """
        Given a readable file object which represents a .svn/entries file in
        format version 8, return the revision as a string.
        """
        entriesFile.readline()
        entriesFile.readline()
        entriesFile.readline()
        return entriesFile.readline().strip()


    def _getSVNVersion(self):
        """
        Figure out the SVN revision number based on the existance of
        <package>/.svn/entries, and its contents. This requires discovering the
        format version from the 'format' file and parsing the entries file
        accordingly.

        @return: None or string containing SVN Revision number.
        """
        mod = sys.modules.get(self.package)
        if mod:
            svn = os.path.join(os.path.dirname(mod.__file__), '.svn')
            formatFile = os.path.join(svn, 'format')
            if not os.path.exists(formatFile):
                return None
            format = file(formatFile).read().strip()
            ent = os.path.join(svn, 'entries')
            if not os.path.exists(ent):
                return None
            parser = getattr(self, '_parseSVNEntries_' + format, None)
            if parser is None:
                return 'Unknown'
            entries = file(ent)
            try:
                try:
                    return parser(entries)
                finally:
                    entries.close()
            except:
                return 'Unknown'


    def _formatSVNVersion(self):
        ver = self._getSVNVersion()
        if ver is None:
            return ''
        return ' (SVN r%s)' % (ver,)



def getVersionString(version):
    """
    Get a friendly string for the given version object.

    @param version: A L{Version} object.
    @return: A string containing the package and short version number.
    """
    return '%s %s' % (version.package, version.short())
