# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2003 Matthew W. Lefkowitz
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
#
"""Save and load Small OBjects to and from files, using various formats.

API Stability: unstable

Maintainer: U{Moshe Zadka<mailto:moshez@twistedmatrix.com>}
"""

import os, md5, sys
try:
    import cPickle as pickle
except ImportError:
    import pickle
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
from twisted.python import components, log, runtime
from twisted.persisted import styles

# Note:
# These encrypt/decrypt functions only work for data formats
# which are immune to having spaces tucked at the end.
# All data formats which persist saves hold that condition.
def _encrypt(passphrase, data):
    from Crypto.Cipher import AES as cipher
    leftover = len(data) % cipher.block_size
    if leftover:
        data += ' '*(cipher.block_size - leftover)
    return cipher.new(md5.new(passphrase).digest()[:16]).encrypt(data)

def _decrypt(passphrase, data):
    from Crypto.Cipher import AES
    return AES.new(md5.new(passphrase).digest()[:16]).decrypt(data)


class IPersistable(components.Interface):

    """An object which can be saved in several formats to a file"""

    def setStyle(self, style):
        """Set desired format.

        @type style: string (one of 'pickle', 'source' or 'xml')
        """

    def save(self, tag=None, filename=None, passphrase=None):
        """Save object to file.

        @type tag: string
        @type filename: string
        @type passphrase: string
        """


class Persistent:

    __implements__ = IPersistable,

    style = "pickle"

    def __init__(self, original, name):
        self.original = original
        self.name = name

    def setStyle(self, style):
        """Set desired format.

        @type style: string (one of 'pickle', 'source' or 'xml')
        """
        self.style = style

    def _getFilename(self, filename, ext, tag):
        if filename:
            finalname = filename
            filename = finalname + "-2"
        elif tag:
            filename = "%s-%s-2.%s" % (self.name, tag, ext)
            finalname = "%s-%s.%s" % (self.name, tag, ext)
        else:
            filename = "%s-2.%s" % (self.name, ext)
            finalname = "%s.%s" % (self.name, ext)
        return finalname, filename

    def _saveTemp(self, filename, passphrase, dumpFunc):
        f = open(filename, 'wb')
        if passphrase is None:
            dumpFunc(self.original, f)
        else:
            s = StringIO.StringIO()
            dumpFunc(self.original, s)
            f.write(_encrypt(passphrase, s.getvalue()))
        f.close()

    def _getStyle(self):
        if self.style == "xml":
            from twisted.persisted.marmalade import jellyToXML as dumpFunc
            ext = "tax"
        elif self.style == "source":
            from twisted.persisted.aot import jellyToSource as dumpFunc
            ext = "tas"
        else:
            def dumpFunc(obj, file):
                pickle.dump(obj, file, 1)
            ext = "tap"
        return ext, dumpFunc

    def save(self, tag=None, filename=None, passphrase=None):
        """Save object to file.

        @type tag: string
        @type filename: string
        @type passphrase: string
        """
        ext, dumpFunc = self._getStyle()
        if passphrase:
            ext = 'e' + ext
        finalname, filename = self._getFilename(filename, ext, tag)
        log.msg("Saving "+self.name+" application to "+finalname+"...")
        self._saveTemp(filename, passphrase, dumpFunc)
        if runtime.platformType == "win32" and os.path.isfile(finalname):
            os.remove(finalname)
        os.rename(filename, finalname)
        log.msg("Saved.")

# "Persistant" has been present since 1.0.7, so retain it for compatibility
Persistant = Persistent

class _EverythingEphemeral(styles.Ephemeral):

    initRun = 0

    def __getattr__(self, key):
        try:
            return getattr(mainMod, key)
        except AttributeError:
            if self.initRun:
                raise
            else:
                log.msg("Warning!  Loading from __main__: %s" % key)
                return styles.Ephemeral()


def load(filename, style, passphrase=None):
    """Load an object from a file.

    Deserialize an object from a file. The file can be encrypted.

    @param filename: string
    @param style: string (one of 'source', 'xml' or 'pickle')
    @param passphrase: string
    """
    mode = 'r'
    if style=='source':
        from twisted.persisted.aot import unjellyFromSource as load
    elif style=='xml':
        from twisted.persisted.marmalade import unjellyFromXML as load
    else:
        load, mode = pickle.load, 'rb'
    if passphrase:
        fp = StringIO.StringIO(_decrypt(passphrase,
                                        open(filename, 'rb').read()))
    else:
        fp = open(filename, mode)
    mainMod = sys.modules['__main__']
    ee = _EverythingEphemeral()
    sys.modules['__main__'] = ee
    ee.initRun = 1
    value = load(fp)
    sys.modules['__main__'] = mainMod
    styles.doUpgrade()
    ee.initRun = 0
    persistable = IPersistable(value, None)
    if persistable is not None:
        persistable.setStyle(style)
    return value


def loadValueFromFile(filename, variable, passphrase=None):
    """Load the value of a variable in a Python file.

    Run the contents of the file, after decrypting if C{passphrase} is
    given, in a namespace and return the result of the variable
    named C{variable}.

    @param filename: string
    @param variable: string
    @param passphrase: string
    """
    if passphrase:
        mode = 'rb'
    else:
        mode = 'r'
    data = open(filename, mode).read()
    if passphrase:
        data = _decrypt(passphrase, data)
    d = {'__file__': filename}
    exec data in d, d
    value = d[variable]
    return value

def guessType(filename):
    ext = os.path.splitext(filename)[1]
    return {
        '.tac':  'python',
        '.etac':  'python',
        '.py':  'python',
        '.tap': 'pickle',
        '.etap': 'pickle',
        '.tas': 'source',
        '.etas': 'source',
        '.tax': 'xml',
        '.etax': 'xml'
    }[ext]

__all__ = ['loadValueFromFile', 'load', 'Persistent', 'Persistant',
           'IPersistable', 'guessType']
