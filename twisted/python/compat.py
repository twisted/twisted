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
Compatability module to provide backwards compatability
for useful Python features.

This is mainly for use of internal Twisted code. We encourage you to use
the latest version of Python directly from your code, if possible.
"""

import types, socket, struct, __builtin__

_dict_doc = (
    """dict() -> new empty dictionary.
    dict(mapping) -> new dictionary initialized from a mapping object's
        (key, value) pairs.
    dict(seq) -> new dictionary initialized as if via:
        d = {}
        for k, v in seq:
            d[k] = v
    dict(**kwargs) -> new dictionary initialized with the name=value pairs
        in the keyword argument list.  For example:  dict(one=1, two=2)
    """)

# Python 2.1 forward-compatibility hacks
try:
    _dict = dict
    d = dict((('a','b'),), c='d')
except NameError:
    # Python 2.1
    def dict(*arg, **kwargs):
        r = {}
        if arg:
            assert len(arg) == 1
            arg = arg[0]
            if hasattr(arg, 'items'):
                r.update(arg)
            else:
                for k, v in arg:
                    r[k] = v
        for k, v in kwargs.items():
            r[k] = v
        return r
    dict.__doc__ = _dict_doc
except TypeError:
    def dict(*arg, **kwargs):
        d = _dict(*arg)
        d.update(kwargs)
        return d
    dict.__doc__ = _dict_doc
else:
    # Python 2.3+
    dict = dict


# This actually injects StringTypes into types!
# is this proper twisted.compat behavior??
try:
    types.StringTypes
except AttributeError:
    types.StringTypes = (types.StringType, types.UnicodeType)

try:
    bool = bool
    True = True
    False = False
except NameError:
    def bool(value):
        """Demote a value to 0 or 1, depending on its truth value

        This is not to be confused with types.BooleanType, which is
        way too hard to duplicate in 2.1 to be worth the trouble.
        """
        return not not value
    True = 1==1
    False = not True

try:
    StopIteration = StopIteration
    iter = iter
except:
    class StopIteration(Exception):
        """Signal the end from iterator.next()."""
        pass

    class _SequenceIterator:
        """
        Facilitates implicit sequence/dict iterability
        """
        def __init__(self, seq):
            self.idx = 0
            # dictionary behavior
            if hasattr(seq, 'keys'):
                seq = seq.keys()
            self.seq = seq

        def __iter__(self):
            return self

        def next(self):
            idx = self.idx
            self.idx += 1
            try:
                return self.seq[idx]
            except IndexError: 
                raise StopIteration

    class _CompatIterator:
        """
        Facilitates for x in iter(iterable)
        """
        def __init__(self, iterable):
            self.iterable = iterable

        def next(self):
            return self.iterable.next()

        def __getitem__(self, index):
            try:
                return self.next()
            except StopIteration, s:
                raise IndexError, s

    class _CompatSentinelIterator(_CompatIterator):
        """
        Facilitates for x in iter(callable, sentinel)
        """
        def __init__(self, callable, sentinel):
            self.callable = callable
            self.sentinel = sentinel

        def next(self):
            res = self.iterable()
            if res == self.sentinel:
                raise StopIteration
            return res
    
    def _iter(iterable):
        if isinstance(iterable, _CompatIterator):
            # already iterable
            return iterable
        if not hasattr(iterable, '__iter__'):
            # implicit iteration, dependent on sequence or dict behavior
            iterable = _SequenceIterator(iterable)
        return _CompatIterator(iterable.__iter__())

    def _iter_sentinel(callable, sentinel):
        if not callable(callable):
            raise TypeError, 'iter(v, w): v must be callable'
        return _CompatSentinelIterator(callable, sentinel)

    def iter(*args): 
        """
        iter(collection) -> iterator
        iter(callable, sentinel) -> iterator

        Get an iterator from an object.  In the first form, the argument must
        supply its own iterator, or be a sequence.
        In the second form, the callable is called until it returns the sentinel.
        """
        if len(args) == 1:
            return _iter(*args)
        elif len(args) == 2:
            return _iter_sentinel(*args)
        raise TypeError, "iter() takes at most 2 arguments (%d given)" % (len(args),)


try:
    from socket import inet_pton, inet_ntop
except ImportError:
    def inet_pton(af, addr):
        if af == socket.AF_INET:
            parts = map(int, addr.split('.'))
            return struct.pack('!BBBB', *parts)
        elif af == socket.AF_INET6:
            parts = addr.split(':')
            elide = parts.count('')
            if elide == 3:
                return '\x00' * 16
            elif elide == 2:
                i = parts.index('')
                parts[i:i+2] = ['0'] * (10 - len(parts))
            elif elide == 1:
                i = parts.index('')
                parts[i:i+1] = ['0'] * (9 - len(parts))
            parts = [int(x, 16) for x in parts]
            return struct.pack('!HHHHHHHH', *parts)
        else:
            raise ValueError, "unsupported address family"


    def inet_ntop(af, addr):
        if af == socket.AF_INET:
            parts = struct.unpack('!BBBB', addr)
            return '.'.join(map(str, parts))
        elif af == socket.AF_INET6:
            parts = struct.unpack('!HHHHHHHH', addr)
            return ':'.join([hex(x)[2:] for x in parts])
        else:
            raise ValueError, "unsupported address family"

try:
    assert isinstance('foo', types.StringTypes)
except TypeError:
    def isinstance(object, class_or_type_or_tuple):
        if type(class_or_type_or_tuple) == types.TupleType:
            for t in class_or_type_or_tuple:
                if __builtin__.isinstance(object, t):
                    return 1
            return 0
        else:
            return __builtin__.isinstance(object, class_or_type_or_tuple)
    assert isinstance('foo', types.StringTypes)
else:
    isinstance = isinstance

__all__ = ['dict', 'inet_pton', 'inet_ntop', 'isinstance', 
           'True', 'False', 'bool', 'StopIteration', 'iter']

#if __name__ == '__main__':
#    print repr(inet_pton(socket.AF_INET, '1.2.3.4'))
#    print repr(inet_pton(socket.AF_INET6, '::'))
#    print repr(inet_pton(socket.AF_INET6, '1:5::2'))
#    print repr(inet_pton(socket.AF_INET6, '::3af:ab45'))
#    print repr(inet_pton(socket.AF_INET6, '1bf0::3af:ab45'))

#    print inet_ntop(socket.AF_INET, inet_pton(socket.AF_INET, '1.2.3.4'))
#    print inet_ntop(socket.AF_INET6, inet_pton(socket.AF_INET6, '::'))
#    print inet_ntop(socket.AF_INET6, inet_pton(socket.AF_INET6, '1:5::2'))
#    print inet_ntop(socket.AF_INET6, inet_pton(socket.AF_INET6, '::3af:ab45'))
#    print inet_ntop(socket.AF_INET6, inet_pton(socket.AF_INET6, '1bf0::3af:ab45'))
