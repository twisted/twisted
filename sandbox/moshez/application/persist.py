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
import os, md5
import cPickle as pickle
import cStringIO as StringIO
from twisted.python import components, log, runtime

def encrypt(passphrase, data):
    from Crypto.Cipher import AES as cipher
    leftover = len(data) % cipher.block_size
    if leftover:
        data += ' '*(cipher.block_size - leftover)
    return cipher.new(md5.new(passphrase).digest()[:16]).encrypt(data)

def decrypt(passphrase, data):
    from Crypto.Cipher import AES
    return AES.new(md5.new(passphrase).digest()[:16]).decrypt(data)


class IPersistable(components.Interface):

    def setPassword(self, password):
        pass
 
    def setStyle(self, style):
        pass

    def save(self, tag=None, filename=None, passphrase=None):
        pass


class Persistant:

    __implements__ = IPersistable,

    style = "pickle"

    def __init__(self, original, name):
        self.original = original
        self.name = name

    def setStyle(self, style):
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
            dumpFunc(self, f)
        else:
            s = StringIO.StringIO()
            dumpFunc(self, s)
            f.write(encrypt(passphrase, s.getvalue()))
        f.close()

    def _getStyle(self):
        if self.style == "xml":
            from twisted.persisted.marmalade import jellyToXML as dumpFunc
            ext = "tax"
        elif self.style == "aot":
            from twisted.persisted.aot import jellyToSource as dumpFunc
            ext = "tas"
        else:
            def dumpFunc(obj, file):
                pickle.dump(obj, file, 1)
            ext = "tap"
        return ext, dumpFunc

    def save(self, tag=None, filename=None, passphrase=None):
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
