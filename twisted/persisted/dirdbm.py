
"""
I am a DBM-style interface to a directory.

Each key is stored as a single file.  This is not expected to be very fast or
efficient, but it's good for easy debugging.
"""


import os
import types
_open = __builtins__['open']

class DirDBM:
    """A directory with a DBM interface.
    This class presents a hash-like interface to a directory of small,
    flat files.
    """
    def __init__(self, name):
        """Initialize.
        """
        self.dname = os.path.abspath(name)
        if not os.path.isdir(self.dname):
            os.mkdir(self.dname)
        
    def __setitem__(self, k, v):
        """dirdbm[foo] = bar; create or modify a textfile in this directory
        """
        assert type(k) == types.StringType
        assert type(v) == types.StringType
        f = _open(os.path.join(self.dname, k),'wb')
        f.write(v)
        f.flush()
        f.close()

    def __getitem__(self, k):
        """dirdbm[foo]; get the contents of a file in this directory as a string
        """
        assert type(k) == types.StringType
        try:    return _open(os.path.join(self.dname, k)).read()
        except: raise KeyError(k)

    def __delitem__(self, k):
        """del dirdbm[foo]; delete a file in this directory
        """
        assert type(k) == types.StringType
        try:    os.remove(os.path.join(self.dname, k))
        except: raise KeyError(k)

    def keys(self):
        """dirdbm.keys(); return a list of filenames
        """
        return os.listdir(self.dname)

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

    def has_key(self, key):
        """dirdbm.has_key(key); return whether the file `key' exists.
        """
        assert type(key) == types.StringType
        return os.path.isfile(os.path.join(self.dname, key))
    
    def update(self, dict):
        """dirdbm.update(dict); update me from another dict-style interface
        """
        for key, val in dict.items():
            self[key]=val
            
    def close(self):
        """close this dbm: no-op, for dbm-style interface compliance
        """


def open(file, flag = None, mode = None):
    """open(file); This is for 'anydbm' compatibility
    """
    return DirDBM(file)
