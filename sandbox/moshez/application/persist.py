import os
import cPickle as pickle
import cStringIO as StringIO
from twisted.python import components

def encrypt(passphrase, data):
    import md5
    from Crypto.Cipher import AES as cipher
    leftover = len(data) % cipher.block_size
    if leftover:
        data = data + ' '*(cipher.block_size - leftover)
    return cipher.new(md5.new(passphrase).digest()[:16]).encrypt(data)


class IPersistable(components.Interface):

    def setPassword(self, password):
        pass
 
    def setStyle(self, style):
        pass

    def save(self, tag=None, filename=None, passphrase=None):
        pass


class Persistant:

    style = "pickle"

    def __init__(self, original, name):
        self.original = original
        self.basename = name

    def _getFilename(self, filename, ext, tag):
        if filename:
            finalname = filename
            filename = finalname + "-2"
        else:
            if tag:
                filename = "%s-%s-2.%s" % (self.name, tag, ext)
                finalname = "%s-%s.%s" % (self.name, tag, ext)
            else:
                filename = "%s-2.%s" % (self.name, ext)
                finalname = "%s.%s" % (self.name, ext)
        return finalname, filename

    def _saveTemp(self, filename, passphrase, dumpFunc):
        if passphrase is None:
            f = open(filename, 'wb')
            dumpFunc(self, f)
            f.flush()
            f.close()
        else:
            f = StringIO.StringIO()
            dumpFunc(self, f)
            s = encrypt(passphrase, f.getvalue())
            f = open(filename, 'wb')
            f.write(s)
            f.flush()
            f.close()

    def _getStyle(self):
        if self.style == "xml":
            from twisted.persisted.marmalade import jellyToXML
            dumpFunc = jellyToXML
            ext = "tax"
        elif self.persistStyle == "aot":
            from twisted.persisted.aot import jellyToSource
            dumpFunc = jellyToSource
            ext = "tas"
        else:
            def dumpFunc(obj, file):
                pickle.dump(obj, file, 1)
            ext = "tap"
        return ext, dumpFunc

    def save(self, tag=None, filename=None, passphrase=None):
        """Save a pickle of this application to a file in the current directory.
        """
        ext, dumpFunc = self._getStyle()
        if passphrase:
            ext = 'e' + ext
        finalname, filename = self._getFilename(filename, ext, tag)
        log.msg("Saving "+self.name+" application to "+finalname+"...")
        self._saveTemp(filename, passphrase, dumpFunc)
        if runtime.platform.getType() == "win32" and os.path.isfile(finalname):
                os.remove(finalname)
        os.rename(filename, finalname)
        log.msg("Saved.")
