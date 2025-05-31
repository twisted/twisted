# -*- test-case-name: twisted.test.test_dirdbm -*-
#
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A L{DirDBM} is a L{dbm}-style interface to a directory.

Each key is stored as a single file.  This is not expected to be very fast or
efficient, but it's good for easy debugging.

L{DirDBM}s are *not* thread-safe, they should only be accessed by one thread at
a time.

No files should be placed in the working directory of a DirDBM save those
created by the DirDBM itself!
"""

from __future__ import annotations

import base64
import glob
import os
import pickle
from typing import AnyStr, Iterable, Mapping, TypeVar, overload

from twisted.python.filepath import FilePath

_T = TypeVar("_T", bound=None)


class DirDBM:
    """
    A directory with a DBM interface.

    This class presents a hash-like interface to a directory of small,
    flat files. It can only use strings as keys or values.
    """

    def __init__(self, name: bytes) -> None:
        """
        @param name: Base path to use for the directory storage.
        """
        self.dname = os.path.abspath(name)
        self._dnamePath = FilePath(name)
        if not self._dnamePath.isdir():
            self._dnamePath.createDirectory()
        else:
            # Run recovery, in case we crashed. we delete all files ending
            # with ".new". Then we find all files who end with ".rpl". If a
            # corresponding file exists without ".rpl", we assume the write
            # failed and delete the ".rpl" file. If only a ".rpl" exist we
            # assume the program crashed right after deleting the old entry
            # but before renaming the replacement entry.
            #
            # NOTE: '.' is NOT in the base64 alphabet!
            for f in glob.glob(self._dnamePath.child("*.new").path):
                os.remove(f)
            replacements = glob.glob(self._dnamePath.child("*.rpl").path)
            for f in replacements:
                old = f[:-4]
                if os.path.exists(old):
                    os.remove(f)
                else:
                    os.rename(f, old)

    def _encode(self, k: bytes) -> bytes:
        """
        Encode a key so it can be used as a filename.
        """
        # NOTE: '_' is NOT in the base64 alphabet!
        return base64.encodebytes(k).replace(b"\n", b"_").replace(b"/", b"-")

    def _decode(self, k: bytes) -> bytes:
        """
        Decode a filename to get the key.
        """
        return base64.decodebytes(k.replace(b"_", b"\n").replace(b"-", b"/"))

    def _readFile(self, path: FilePath[AnyStr]) -> bytes:
        """
        Read in the contents of a file.

        Override in subclasses to e.g. provide transparently encrypted dirdbm.
        """
        with path.open() as f:
            s = f.read()
        return s

    def _writeFile(self, path: FilePath[AnyStr], data: bytes) -> None:
        """
        Write data to a file.

        Override in subclasses to e.g. provide transparently encrypted dirdbm.
        """
        with path.open("w") as f:
            f.write(data)
            f.flush()

    def __len__(self) -> int:
        """
        @return: The number of key/value pairs in this Shelf
        """
        return len(self._dnamePath.listdir())

    def __setitem__(self, k: bytes, v: bytes) -> None:
        """
        C{dirdbm[k] = v}
        Create or modify a textfile in this directory

        @type k: bytes
        @param k: key to set

        @type v: bytes
        @param v: value to associate with C{k}
        """
        if not type(k) == bytes:
            raise TypeError("DirDBM key must be bytes")
        if not type(v) == bytes:
            raise TypeError("DirDBM value must be bytes")
        k = self._encode(k)

        # We create a new file with extension .new, write the data to it, and
        # if the write succeeds delete the old file and rename the new one.
        old = self._dnamePath.child(k)
        if old.exists():
            new = old.siblingExtension(".rpl")  # Replacement entry
        else:
            new = old.siblingExtension(".new")  # New entry
        try:
            self._writeFile(new, v)
        except BaseException:
            new.remove()
            raise
        else:
            if old.exists():
                old.remove()
            new.moveTo(old)

    def __getitem__(self, k: bytes) -> bytes:
        """
        C{dirdbm[k]} Get the contents of a file in this directory as a string.

        @param k: key to lookup

        @return: The value associated with C{k}

        @raise KeyError: Raised when there is no such key
        """
        if not type(k) == bytes:
            raise TypeError("DirDBM key must be bytes")
        path = self._dnamePath.child(self._encode(k))
        try:
            return self._readFile(path)
        except OSError:
            raise KeyError(k)

    def __delitem__(self, k: bytes) -> None:
        """
        C{del dirdbm[foo]}
        Delete a file in this directory.

        @type k: bytes
        @param k: key to delete

        @raise KeyError: Raised when there is no such key
        """
        if not type(k) == bytes:
            raise TypeError("DirDBM key must be bytes")
        k = self._encode(k)
        try:
            self._dnamePath.child(k).remove()
        except OSError:
            raise KeyError(self._decode(k))

    def keys(self) -> Iterable[bytes]:
        """
        @return: a L{list} of filenames (keys).
        """
        return list(map(self._decode, self._dnamePath.asBytesMode().listdir()))

    def values(self) -> Iterable[bytes]:
        """
        @return: a L{list} of file-contents (values).
        """
        vals = []
        keys = self.keys()
        for key in keys:
            vals.append(self[key])
        return vals

    def items(self) -> Iterable[tuple[bytes, bytes]]:
        """
        @return: a L{list} of 2-tuples containing key/value pairs.
        """
        items = []
        keys = self.keys()
        for key in keys:
            items.append((key, self[key]))
        return items

    def has_key(self, key: bytes) -> bool:
        """
        @type key: bytes
        @param key: The key to test

        @return: A true value if this dirdbm has the specified key, a false
        value otherwise.
        """
        if not type(key) == bytes:
            raise TypeError("DirDBM key must be bytes")
        key = self._encode(key)
        return self._dnamePath.child(key).isfile()

    def setdefault(self, key: bytes, value: bytes) -> bytes:
        """
        @type key: bytes
        @param key: The key to lookup

        @param value: The value to associate with key if key is not already
        associated with a value.
        """
        if key not in self:
            self[key] = value
            return value
        return self[key]

    @overload
    def get(self, key: bytes) -> bytes:
        ...

    @overload
    def get(self, key: bytes, default: _T) -> bytes | _T:
        ...

    def get(self, key: bytes, default: _T | None = None) -> bytes | _T | None:
        """
        @param key: The key to lookup

        @param default: The value to return if the given key does not exist

        @return: The value associated with C{key} or C{default} if not
            L{DirDBM.has_key(key)}
        """
        if key in self:
            return self[key]
        else:
            return default

    def __contains__(self, key: bytes) -> bool:
        """
        @see: L{DirDBM.has_key}
        """
        return self.has_key(key)

    def update(self, other: Mapping[bytes, bytes]) -> None:
        """
        Add all the key/value pairs in L{dict} to this dirdbm.  Any conflicting
        keys will be overwritten with the values from L{dict}.

        @param dict: A mapping of key/value pairs to add to this dirdbm.
        """
        for key, val in other.items():
            self[key] = val

    def copyTo(self, path: bytes) -> DirDBM:
        """
        Copy the contents of this dirdbm to the dirdbm at C{path}.

        @param path: The path of the dirdbm to copy to.  If a dirdbm
        exists at the destination path, it is cleared first.

        @rtype: C{DirDBM}
        @return: The dirdbm this dirdbm was copied to.
        """
        fpath = FilePath(path)
        assert fpath != self._dnamePath

        d = self.__class__(fpath.path)
        d.clear()
        for k in self.keys():
            d[k] = self[k]
        return d

    def clear(self) -> None:
        """
        Delete all key/value pairs in this dirdbm.
        """
        for k in self.keys():
            del self[k]

    def close(self) -> None:
        """
        Close this dbm: no-op, for dbm-style interface compliance.
        """

    def getModificationTime(self, key: bytes) -> float:
        """
        Returns modification time of an entry.

        @return: Last modification date (seconds since epoch) of entry C{key}
        @raise KeyError: Raised when there is no such key
        """
        if not type(key) == bytes:
            raise TypeError("DirDBM key must be bytes")
        path = self._dnamePath.child(self._encode(key))
        if path.isfile():
            return path.getModificationTime()
        else:
            raise KeyError(key)


class Shelf(DirDBM):
    """
    A directory with a DBM shelf interface.

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

        @type k: bytes
        @param k: The key to lookup

        @return: The value associated with the given key
        @raise KeyError: Raised if the given key does not exist
        """
        return pickle.loads(DirDBM.__getitem__(self, k))


def open(file, flag=None, mode=None):
    """
    This is for 'anydbm' compatibility.

    @param file: The parameter to pass to the DirDBM constructor.

    @param flag: ignored
    @param mode: ignored
    """
    return DirDBM(file)


__all__ = ["open", "DirDBM", "Shelf"]
