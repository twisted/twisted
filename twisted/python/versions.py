# -*- test-case-name: twisted.test.test_versions -*-
# Copyright (c) 2006 Twisted Matrix Laboratories.
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
            s += '+r'+svnver
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
            raise IncomparableVersions()
        return cmp((self.major,
                    self.minor,
                    self.micro),
                   (other.major,
                    other.minor,
                    other.micro))


    def _parseSVNEntries(self, entriesFile):
        """
        Given a readable file object which represents a .svn/entries
        file, return the revision as a string. If the file cannot be
        parsed, return the string "Unknown".
        """
        try:
            from xml.dom.minidom import parse
            doc = parse(entriesFile).documentElement
            for node in doc.childNodes:
                if hasattr(node, 'getAttribute'):
                    rev = node.getAttribute('revision')
                    if rev is not None:
                        return rev.encode('ascii')
        except:
            return "Unknown"
        

    def _getSVNVersion(self):
        """
        Figure out the SVN revision number based on the existance of
        twisted/.svn/entries, and its contents. This requires parsing the
        entries file and reading the first XML tag in the xml document that has
        a revision="" attribute.

        @return: None or string containing SVN Revision number.
        """
        mod = sys.modules.get(self.package)
        if mod:
            ent = os.path.join(os.path.dirname(mod.__file__),
                               '.svn',
                               'entries')
            if os.path.exists(ent):
                return self._parseSVNEntries(open(ent))


    def _formatSVNVersion(self):
        ver = self._getSVNVersion()
        if ver is None:
            return ''
        return ' (SVN r%s)' % (ver,)
