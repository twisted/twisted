# -*- test-case-name: twisted.test.test_compat -*-
#
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Compatibility module to provide backwards compatibility for useful Python
features.

This is mainly for use of internal Twisted code. We encourage you to use
the latest version of Python directly from your code, if possible.

@var unicode: The type of Unicode strings, C{unicode} on Python 2 and C{str}
    on Python 3.

@var NativeStringIO: An in-memory file-like object that operates on the native
    string type (bytes in Python 2, unicode in Python 3).
"""

from __future__ import division

import sys, string, socket, struct, inspect
from io import TextIOBase, IOBase


if sys.version_info < (3, 0):
    _PY3 = False
else:
    _PY3 = True



def currentframe(n=0):
    """
    In Python 3, L{inspect.currentframe} does not take a stack-level argument.
    Restore that functionality from Python 2 so we don't have to re-implement
    the C{f_back}-walking loop in places where it's called.

    @param n: The number of stack levels above the caller to walk.
    @type n: L{int}

    @return: a frame, n levels up the stack from the caller.
    @rtype: L{types.FrameType}
    """
    f = inspect.currentframe()
    for x in range(n + 1):
        f = f.f_back
    return f



def inet_pton(af, addr):
    if af == socket.AF_INET:
        return socket.inet_aton(addr)
    elif af == getattr(socket, 'AF_INET6', 'AF_INET6'):
        if [x for x in addr if x not in string.hexdigits + ':.']:
            raise ValueError("Illegal characters: %r" % (''.join(x),))

        parts = addr.split(':')
        elided = parts.count('')
        ipv4Component = '.' in parts[-1]

        if len(parts) > (8 - ipv4Component) or elided > 3:
            raise ValueError("Syntactically invalid address")

        if elided == 3:
            return '\x00' * 16

        if elided:
            zeros = ['0'] * (8 - len(parts) - ipv4Component + elided)

            if addr.startswith('::'):
                parts[:2] = zeros
            elif addr.endswith('::'):
                parts[-2:] = zeros
            else:
                idx = parts.index('')
                parts[idx:idx+1] = zeros

            if len(parts) != 8 - ipv4Component:
                raise ValueError("Syntactically invalid address")
        else:
            if len(parts) != (8 - ipv4Component):
                raise ValueError("Syntactically invalid address")

        if ipv4Component:
            if parts[-1].count('.') != 3:
                raise ValueError("Syntactically invalid address")
            rawipv4 = socket.inet_aton(parts[-1])
            unpackedipv4 = struct.unpack('!HH', rawipv4)
            parts[-1:] = [hex(x)[2:] for x in unpackedipv4]

        parts = [int(x, 16) for x in parts]
        return struct.pack('!8H', *parts)
    else:
        raise socket.error(97, 'Address family not supported by protocol')

def inet_ntop(af, addr):
    if af == socket.AF_INET:
        return socket.inet_ntoa(addr)
    elif af == socket.AF_INET6:
        if len(addr) != 16:
            raise ValueError("address length incorrect")
        parts = struct.unpack('!8H', addr)
        curBase = bestBase = None
        for i in range(8):
            if not parts[i]:
                if curBase is None:
                    curBase = i
                    curLen = 0
                curLen += 1
            else:
                if curBase is not None:
                    bestLen = None
                    if bestBase is None or curLen > bestLen:
                        bestBase = curBase
                        bestLen = curLen
                    curBase = None
        if curBase is not None and (bestBase is None or curLen > bestLen):
            bestBase = curBase
            bestLen = curLen
        parts = [hex(x)[2:] for x in parts]
        if bestBase is not None:
            parts[bestBase:bestBase + bestLen] = ['']
        if parts[0] == '':
            parts.insert(0, '')
        if parts[-1] == '':
            parts.insert(len(parts) - 1, '')
        return ':'.join(parts)
    else:
        raise socket.error(97, 'Address family not supported by protocol')

try:
    socket.AF_INET6
except AttributeError:
    socket.AF_INET6 = 'AF_INET6'

try:
    socket.inet_pton(socket.AF_INET6, "::")
except (AttributeError, NameError, socket.error):
    socket.inet_pton = inet_pton
    socket.inet_ntop = inet_ntop


adict = dict



if _PY3:
    # These are actually useless in Python 2 as well, but we need to go
    # through deprecation process there (ticket #5895):
    del adict, inet_pton, inet_ntop


set = set
frozenset = frozenset


try:
    from functools import reduce
except ImportError:
    reduce = reduce



def execfile(filename, globals, locals=None):
    """
    Execute a Python script in the given namespaces.

    Similar to the execfile builtin, but a namespace is mandatory, partly
    because that's a sensible thing to require, and because otherwise we'd
    have to do some frame hacking.

    This is a compatibility implementation for Python 3 porting, to avoid the
    use of the deprecated builtin C{execfile} function.
    """
    if locals is None:
        locals = globals
    fin = open(filename, "rbU")
    try:
        source = fin.read()
    finally:
        fin.close()
    code = compile(source, filename, "exec")
    exec(code, globals, locals)


try:
    cmp = cmp
except NameError:
    def cmp(a, b):
        """
        Compare two objects.

        Returns a negative number if C{a < b}, zero if they are equal, and a
        positive number if C{a > b}.
        """
        if a < b:
            return -1
        elif a == b:
            return 0
        else:
            return 1



def comparable(klass):
    """
    Class decorator that ensures support for the special C{__cmp__} method.

    On Python 2 this does nothing.

    On Python 3, C{__eq__}, C{__lt__}, etc. methods are added to the class,
    relying on C{__cmp__} to implement their comparisons.
    """
    # On Python 2, __cmp__ will just work, so no need to add extra methods:
    if not _PY3:
        return klass

    def __eq__(self, other):
        c = self.__cmp__(other)
        if c is NotImplemented:
            return c
        return c == 0


    def __ne__(self, other):
        c = self.__cmp__(other)
        if c is NotImplemented:
            return c
        return c != 0


    def __lt__(self, other):
        c = self.__cmp__(other)
        if c is NotImplemented:
            return c
        return c < 0


    def __le__(self, other):
        c = self.__cmp__(other)
        if c is NotImplemented:
            return c
        return c <= 0


    def __gt__(self, other):
        c = self.__cmp__(other)
        if c is NotImplemented:
            return c
        return c > 0


    def __ge__(self, other):
        c = self.__cmp__(other)
        if c is NotImplemented:
            return c
        return c >= 0

    klass.__lt__ = __lt__
    klass.__gt__ = __gt__
    klass.__le__ = __le__
    klass.__ge__ = __ge__
    klass.__eq__ = __eq__
    klass.__ne__ = __ne__
    return klass



if _PY3:
    unicode = str
else:
    unicode = unicode



def ioType(fileIshObject, default=unicode):
    """
    Determine the type which will be returned from the given file object's
    read() and accepted by its write() method as an argument.

    In other words, determine whether the given file is 'opened in text mode'.

    @param fileIshObject: Any object, but ideally one which resembles a file.
    @type fileIshObject: L{object}

    @param default: A default value to return when the type of C{fileIshObject}
        cannot be determined.
    @type default: L{type}

    @return: There are 3 possible return values:

            1. L{unicode}, if the file is unambiguously opened in text mode.

            2. L{bytes}, if the file is unambiguously opened in binary mode.

            3. L{basestring}, if we are on python 2 (the L{basestring} type
               does not exist on python 3) and the file is opened in binary
               mode, but has an encoding and can therefore accept both bytes
               and text reliably for writing, but will return L{bytes} from
               read methods.

            4. The C{default} parameter, if the given type is not understood.

    @rtype: L{type}
    """
    if isinstance(fileIshObject, TextIOBase):
        # If it's for text I/O, then it's for text I/O.
        return unicode
    if isinstance(fileIshObject, IOBase):
        # If it's for I/O but it's _not_ for text I/O, it's for bytes I/O.
        return bytes
    encoding = getattr(fileIshObject, 'encoding', None)
    import codecs
    if isinstance(fileIshObject, (codecs.StreamReader, codecs.StreamWriter)):
        # On StreamReaderWriter, the 'encoding' attribute has special meaning;
        # it is unambiguously unicode.
        if encoding:
            return unicode
        else:
            return bytes
    if not _PY3:
        # Special case: if we have an encoding file, we can *give* it unicode,
        # but we can't expect to *get* unicode.
        if isinstance(fileIshObject, file):
            if encoding is not None:
                return basestring
            else:
                return bytes
        from cStringIO import InputType, OutputType
        from StringIO import StringIO
        if isinstance(fileIshObject, (StringIO, InputType, OutputType)):
            return bytes
    return default



def nativeString(s):
    """
    Convert C{bytes} or C{unicode} to the native C{str} type, using ASCII
    encoding if conversion is necessary.

    @raise UnicodeError: The input string is not ASCII encodable/decodable.
    @raise TypeError: The input is neither C{bytes} nor C{unicode}.
    """
    if not isinstance(s, (bytes, unicode)):
        raise TypeError("%r is neither bytes nor unicode" % s)
    if _PY3:
        if isinstance(s, bytes):
            return s.decode("ascii")
        else:
            # Ensure we're limited to ASCII subset:
            s.encode("ascii")
    else:
        if isinstance(s, unicode):
            return s.encode("ascii")
        else:
            # Ensure we're limited to ASCII subset:
            s.decode("ascii")
    return s



if _PY3:
    def reraise(exception, traceback):
        raise exception.with_traceback(traceback)
else:
    exec("""def reraise(exception, traceback):
        raise exception.__class__, exception, traceback""")

reraise.__doc__ = """
Re-raise an exception, with an optional traceback, in a way that is compatible
with both Python 2 and Python 3.

Note that on Python 3, re-raised exceptions will be mutated, with their
C{__traceback__} attribute being set.

@param exception: The exception instance.
@param traceback: The traceback to use, or C{None} indicating a new traceback.
"""



if _PY3:
    from io import StringIO as NativeStringIO
else:
    from io import BytesIO as NativeStringIO



# Functions for dealing with Python 3's bytes type, which is somewhat
# different than Python 2's:
if _PY3:
    def iterbytes(originalBytes):
        for i in range(len(originalBytes)):
            yield originalBytes[i:i+1]


    def intToBytes(i):
        return ("%d" % i).encode("ascii")


    # Ideally we would use memoryview, but it has a number of differences from
    # the Python 2 buffer() that make that impractical
    # (http://bugs.python.org/issue15945, incompatibility with pyOpenSSL due to
    # PyArg_ParseTuple differences.)
    def lazyByteSlice(object, offset=0, size=None):
        """
        Return a copy of the given bytes-like object.

        If an offset is given, the copy starts at that offset. If a size is
        given, the copy will only be of that length.

        @param object: C{bytes} to be copied.

        @param offset: C{int}, starting index of copy.

        @param size: Optional, if an C{int} is given limit the length of copy
            to this size.
        """
        if size is None:
            return object[offset:]
        else:
            return object[offset:(offset + size)]


    def networkString(s):
        if not isinstance(s, unicode):
            raise TypeError("Can only convert text to bytes on Python 3")
        return s.encode('ascii')
else:
    def iterbytes(originalBytes):
        return originalBytes


    def intToBytes(i):
        return b"%d" % i


    lazyByteSlice = buffer

    def networkString(s):
        if not isinstance(s, str):
            raise TypeError("Can only pass-through bytes on Python 2")
        # Ensure we're limited to ASCII subset:
        s.decode('ascii')
        return s

iterbytes.__doc__ = """
Return an iterable wrapper for a C{bytes} object that provides the behavior of
iterating over C{bytes} on Python 2.

In particular, the results of iteration are the individual bytes (rather than
integers as on Python 3).

@param originalBytes: A C{bytes} object that will be wrapped.
"""

intToBytes.__doc__ = """
Convert the given integer into C{bytes}, as ASCII-encoded Arab numeral.

In other words, this is equivalent to calling C{bytes} in Python 2 on an
integer.

@param i: The C{int} to convert to C{bytes}.
@rtype: C{bytes}
"""

networkString.__doc__ = """
Convert the native string type to C{bytes} if it is not already C{bytes} using
ASCII encoding if conversion is necessary.

This is useful for sending text-like bytes that are constructed using string
interpolation.  For example, this is safe on Python 2 and Python 3:

    networkString("Hello %d" % (n,))

@param s: A native string to convert to bytes if necessary.
@type s: C{str}

@raise UnicodeError: The input string is not ASCII encodable/decodable.
@raise TypeError: The input is neither C{bytes} nor C{unicode}.

@rtype: C{bytes}
"""


try:
    StringType = basestring
except NameError:
    # Python 3+
    StringType = str

try:
    from types import InstanceType
except ImportError:
    # Python 3+
    InstanceType = object

try:
    from types import FileType
except ImportError:
    # Python 3+
    FileType = IOBase



# Dealing with the differences in items/iteritems
if _PY3:
    def iteritems(d):
        return d.items()

    def items(d):
        return list(d.items())

    xrange = range
else:
    def iteritems(d):
        return d.iteritems()

    def items(d):
        return d.items()

    xrange = xrange


iteritems.__doc__ = """
Return an iterable of the items of C{d}.

@type d: L{dict}
@rtype: iterable
"""

items.__doc__ = """
Return a list of the items of C{d}.

@type d: L{dict}
@rtype: L{list}
"""



__all__ = [
    "reraise",
    "execfile",
    "frozenset",
    "reduce",
    "set",
    "cmp",
    "comparable",
    "nativeString",
    "NativeStringIO",
    "networkString",
    "unicode",
    "iterbytes",
    "intToBytes",
    "lazyByteSlice",
    "StringType",
    "InstanceType",
    "FileType",
    "items",
    "iteritems",
    "xrange",
]
