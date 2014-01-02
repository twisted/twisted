# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A simple Python wrapper for pmap_set(3) and pmap_unset(3).
"""

__all__ = ["set", "unset"]

import cffi

source = """
    typedef int bool_t;
    bool_t pmap_set(unsigned long prognum, unsigned long versnum, unsigned int protocol, unsigned short port);
    bool_t pmap_unset(unsigned long prognum, unsigned long versnum);
"""

_ffi = cffi.FFI()
_ffi.cdef(source)
_lib = _ffi.verify(source="#include <rpc/rpc.h>\n" + source)


def set(program, version, protocol, port):
    """
    Set an entry in the portmapper.
    """
    return _lib.pmap_set(program, version, protocol, port)



def unset(program, version):
    """
    Unset an entry in the portmapper.
    """
    return _lib.pmap_unset(program, version)
