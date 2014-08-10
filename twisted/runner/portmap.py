# -*- test-case-name: twisted.runner.test.test_portmap -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A simple Python wrapper for pmap_set(3) and pmap_unset(3).
"""

__all__ = ["set", "unset"]

from functools import wraps

import cffi

_source = """
    typedef int bool_t;
    bool_t pmap_set(unsigned long prognum, unsigned long versnum, unsigned int protocol, unsigned short port);
    bool_t pmap_unset(unsigned long prognum, unsigned long versnum);
"""

_ffi = cffi.FFI()
_ffi.cdef(_source)
_lib = _ffi.verify(
    source="#include <rpc/rpc.h>\n" + _source,
    ext_package="twisted.runner"
)


def _alias(realFunction):
    """
    Create a decorator that makes the decorated function alias for some other
    function.

    @param realFunction: The result of applying the decorator this function
        returns will be this object.
    """
    # An extra Python-defined function is required because the callable object
    # given by cffi may not have a writeable __doc__ attribute.
    @wraps(realFunction)
    def passthrough(*args, **kwargs):
        return realFunction(*args, **kwargs)

    # Make the original available so that unit tests for application code using
    # this decorator are easier to write.
    passthrough.target = realFunction

    def decorator(stubFunction):
        passthrough.__doc__ = stubFunction.__doc__

        return passthrough
    return decorator



@_alias(_lib.pmap_set)
def set(program, version, protocol, port):
    """
    Set an entry in the portmapper.
    """



@_alias(_lib.pmap_unset)
def unset(program, version):
    """
    Unset an entry in the portmapper.
    """
