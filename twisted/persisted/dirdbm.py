
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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


"""
I am a DBM-style interface to a directory.

Each key is stored as a single file.  This is not expected to be very fast or
efficient, but it's good for easy debugging.

DirDBMs are *not* thread-safe, they should only be accessed by one thread at
a time.
"""


import os
import types
import base64
import string
import glob
import cPickle
_open = open

class DirDBM:
    """A directory with a DBM interface.
    
    This class presents a hash-like interface to a directory of small,
    flat files. It can only use strings as keys or values.
    """
    
    def __init__(self, name):
        """Initialize.
        """
        self.dname = os.path.abspath(name)
        if not os.path.isdir(self.dname):
            os.mkdir(self.dname)
        else:
            # Run recovery, in case we crashed. we delete all files ending
            # with ".new". Then we find all files who end with ".rpl". If a
            # corresponding file exists without ".rpl", we assume the write
            # failed and delete the ".rpl" file. If only a ".rpl" exist we
            # assume the program crashed right after deleting the old entry
            # but before renaming the replacement entry.
            #
            # NOTE: '.' is NOT in the base64 alphabet!
            for f in glob.glob(os.path.join(self.dname, "*.new")):
                os.remove(f)
            replacements = glob.glob(os.path.join(self.dname, "*.rpl"))
            for f in replacements:
                old = f[:-4]
                if os.path.exists(old):
                    os.remove(f)
                else:
                    os.rename(f, old)
    
    def _encode(self, k):
        """Encode a key so it can be used as a filename.
        """
        # NOTE: '_' is NOT in the base64 alphabet!
        return string.replace(base64.encodestring(k), '\n', '_')
    
    def _decode(self, k):
        """Decode a filename to get the key.
        """
        return base64.decodestring(string.replace(k, '_', '\n'))
    
    def _readFile(self, path):
        """Read in the contents of a file.
        
        Override in subclasses to e.g. provide transparently encrypted dirdbm.
        """
        f = _open(path, "rb")
        s = f.read()
        f.close()
        return s
    
    def _writeFile(self, path, data):
        """Write data to a file.
        
        Override in subclasses to e.g. provide transparently encrypted dirdbm.
        """
        f = _open(path, "wb")
        f.write(data)
        f.flush()
        f.close()
    
    def __setitem__(self, k, v):
        """dirdbm[foo] = bar; create or modify a textfile in this directory
        """
        assert type(k) == types.StringType
        assert type(v) == types.StringType
        k = self._encode(k)
        
        # we create a new file with extension .new, write the data to it, and
        # if the write succeeds delete the old file and rename the new one.
        old = os.path.join(self.dname, k)
        if os.path.exists(old):
            new = old + ".rpl" # replacement entry
        else:
            new = old + ".new" # new entry
        try:
            self._writeFile(new, v)
        except:
            os.remove(new)
            raise
        else:
            if os.path.exists(old): os.remove(old)
            os.rename(new, old)

    def __getitem__(self, k):
        """dirdbm[foo]; get the contents of a file in this directory as a string
        """
        assert type(k) == types.StringType
        path = os.path.join(self.dname, self._encode(k))
        try:
            return self._readFile(path)
        except:
            raise KeyError, k

    def __delitem__(self, k):
        """del dirdbm[foo]; delete a file in this directory
        """
        assert type(k) == types.StringType
        k = self._encode(k)
        try:    os.remove(os.path.join(self.dname, k))
        except (OSError, IOError): raise KeyError(self._decode(k))

    def keys(self):
        """dirdbm.keys(); return a list of filenames
        """
        return map(self._decode, os.listdir(self.dname))

    def values(self):
        """dirdbm.values(); return a list of file-contents
        """
        vals = []
        keys = self.keys()
        for key in keys:
            vals.append(self[key])
        return vals

    def items(self):
        """dirdbm.items(); return an interspersed list of tuples of keys() and values()
        """
        items = []
        keys = self.keys()
        for key in keys:
            items.append((key, self[key]))
        return items

    def has_key(self, key):
        """dirdbm.has_key(key); return whether the file `key' exists.
        """
        assert type(key) == types.StringType
        key = self._encode(key)
        return os.path.isfile(os.path.join(self.dname, key))
    
    def update(self, dict):
        """dirdbm.update(dict); update me from another dict-style interface
        """
        for key, val in dict.items():
            self[key]=val
            
    def close(self):
        """close this dbm: no-op, for dbm-style interface compliance
        """


class Shelf(DirDBM):
    """A directory with a DBM shelf interface.
    
    This class presents a hash-like interface to a directory of small,
    flat files. Keys must be strings, but values can be any given object.
    """
    
    def __setitem__(self, k, v):
        """shelf[foo] = bar; create or modify a textfile in this directory
        """
        v = cPickle.dumps(v)
        DirDBM.__setitem__(self, k, v)

    def __getitem__(self, k):
        """dirdbm[foo]; get the contents of a file in this directory as a pickle
        """
        return cPickle.loads(DirDBM.__getitem__(self, k))


def open(file, flag = None, mode = None):
    """open(file); This is for 'anydbm' compatibility
    """
    return DirDBM(file)


__all__ = ["open", "DirDBM", "Shelf"]
