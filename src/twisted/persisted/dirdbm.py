# -*- test-case-name: twisted.test.test_dirdbm -*-
#
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.



"""
DBM-style interface to a directory.

Each key is stored as a single file.  This is not expected to be very fast or
efficient, but it's good for easy debugging.

DirDBMs are *not* thread-safe, they should only be accessed by one thread at
a time.

No files should be placed in the working directory of a DirDBM save those
created by the DirDBM itself!

Maintainer: Itamar Shtull-Trauring
"""


import os
import types
import base64
import glob

try:
    import cPickle as pickle
except ImportError:
    import pickle

try:
    _open
except NameError:
    _open = open


class DirDBM:
    """A directory with a DBM interface.
    
    This class presents a hash-like interface to a directory of small,
    flat files. It can only use strings as keys or values.
    """
    
    def __init__(self, name):
        """
        @type name: str
        @param name: Base path to use for the directory storage.
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
        return base64.encodestring(k).replace('\n', '_').replace("/", "-")
    
    def _decode(self, k):
        """Decode a filename to get the key.
        """
        return base64.decodestring(k.replace('_', '\n').replace("-", "/"))
    
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
    
    def __len__(self):
        """
        @return: The number of key/value pairs in this Shelf
        """
        return len(os.listdir(self.dname))

    def __setitem__(self, k, v):
        """
        C{dirdbm[k] = v}
        Create or modify a textfile in this directory

        @type k: str
        @param k: key to set
        
        @type v: str
        @param v: value to associate with C{k}
        """
        assert type(k) == types.StringType, "DirDBM key must be a string"
        assert type(v) == types.StringType, "DirDBM value must be a string"
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
        """
        C{dirdbm[k]}
        Get the contents of a file in this directory as a string.
        
        @type k: str
        @param k: key to lookup
        
        @return: The value associated with C{k}
        @raise KeyError: Raised when there is no such key
        """
        assert type(k) == types.StringType, "DirDBM key must be a string"
        path = os.path.join(self.dname, self._encode(k))
        try:
            return self._readFile(path)
        except:
            raise KeyError, k

    def __delitem__(self, k):
        """
        C{del dirdbm[foo]}
        Delete a file in this directory.
        
        @type k: str
        @param k: key to delete
        
        @raise KeyError: Raised when there is no such key
        """
        assert type(k) == types.StringType, "DirDBM key must be a string"
        k = self._encode(k)
        try:    os.remove(os.path.join(self.dname, k))
        except (OSError, IOError): raise KeyError(self._decode(k))

    def keys(self):
        """
        @return: a C{list} of filenames (keys).
        """
        return map(self._decode, os.listdir(self.dname))

    def values(self):
        """
        @return: a C{list} of file-contents (values).
        """
        vals = []
        keys = self.keys()
        for key in keys:
            vals.append(self[key])
        return vals

    def items(self):
        """
        @return: a C{list} of 2-tuples containing key/value pairs.
        """
        items = []
        keys = self.keys()
        for key in keys:
            items.append((key, self[key]))
        return items

    def has_key(self, key):
        """
        @type key: str
        @param key: The key to test
        
        @return: A true value if this dirdbm has the specified key, a faluse
        value otherwise.
        """
        assert type(key) == types.StringType, "DirDBM key must be a string"
        key = self._encode(key)
        return os.path.isfile(os.path.join(self.dname, key))

    def setdefault(self, key, value):
        """
        @type key: str
        @param key: The key to lookup
        
        @param value: The value to associate with key if key is not already
        associated with a value.
        """
        if not self.has_key(key):
            self[key] = value
            return value
        return self[key]

    def get(self, key, default = None):
        """
        @type key: str
        @param key: The key to lookup
        
        @param default: The value to return if the given key does not exist
        
        @return: The value associated with C{key} or C{default} if not
        C{self.has_key(key)}
        """
        if self.has_key(key):
            return self[key]
        else:
            return default

    def __contains__(self, key):
        """
        C{key in dirdbm}

        @type key: str
        @param key: The key to test
                
        @return: A true value if C{self.has_key(key)}, a false value otherwise.
        """
        assert type(key) == types.StringType, "DirDBM key must be a string"
        key = self._encode(key)
        return os.path.isfile(os.path.join(self.dname, key))

    def update(self, dict):
        """
        Add all the key/value pairs in C{dict} to this dirdbm.  Any conflicting
        keys will be overwritten with the values from C{dict}.

        @type dict: mapping
        @param dict: A mapping of key/value pairs to add to this dirdbm.
        """
        for key, val in dict.items():
            self[key]=val
            
    def copyTo(self, path):
        """
        Copy the contents of this dirdbm to the dirdbm at C{path}.
        
        @type path: C{str}
        @param path: The path of the dirdbm to copy to.  If a dirdbm
        exists at the destination path, it is cleared first.
        
        @rtype: C{DirDBM}
        @return: The dirdbm this dirdbm was copied to.
        """
        path = os.path.abspath(path)
        assert path != self.dname
        
        d = self.__class__(path)
        d.clear()
        for k in self.keys():
            d[k] = self[k]
        return d

    def clear(self):
        """
        Delete all key/value pairs in this dirdbm.
        """
        for k in self.keys():
            del self[k]

    def close(self):
        """
        Close this dbm: no-op, for dbm-style interface compliance.
        """

    def getModificationTime(self, key):
        """
        Returns modification time of an entry.
        
        @return: Last modification date (seconds since epoch) of entry C{key}
        @raise KeyError: Raised when there is no such key
        """
        assert type(key) == types.StringType, "DirDBM key must be a string"
        path = os.path.join(self.dname, self._encode(key))
        if os.path.isfile(path):
            return os.path.getmtime(path)
        else:
            raise KeyError, key


class Shelf(DirDBM):
    """A directory with a DBM shelf interface.
    
    This class presents a hash-like interface to a directory of small,
    flat files. Keys must be strings, but values can be any given object.
    """
    
    def __setitem__(self, k, v):
        """
        C{shelf[foo] = bar}
        Create or modify a textfile in this directory.

        @type k: str
        @param k: The key to set

        @param v: The value to associate with C{key}
        """
        v = pickle.dumps(v)
        DirDBM.__setitem__(self, k, v)

    def __getitem__(self, k):
        """
        C{dirdbm[foo]}
        Get and unpickle the contents of a file in this directory.
        
        @type k: str
        @param k: The key to lookup
        
        @return: The value associated with the given key
        @raise KeyError: Raised if the given key does not exist
        """
        return pickle.loads(DirDBM.__getitem__(self, k))


def open(file, flag = None, mode = None):
    """
    This is for 'anydbm' compatibility.
    
    @param file: The parameter to pass to the DirDBM constructor.

    @param flag: ignored
    @param mode: ignored
    """
    return DirDBM(file)


__all__ = ["open", "DirDBM", "Shelf"]
