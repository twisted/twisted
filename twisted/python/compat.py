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

import socket, struct, __builtin__


# Python 2.1 forward-compatibility hacks
try:
    dict = dict
except NameError:
    def dict(args):
        r = {}
        for (k, v) in args:
            r[k] = v
        return r

import types
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
   class StopIteration(Exception): pass
   class _ListIterator:
       def __init__(self,lst):
           self.idx = 0
           if getattr(lst,'keys',None): lst = lst.keys()
           self.lst = lst
       def next(self):
           idx = self.idx
           self.idx += 1
           try:
               return self.lst[idx]
           except IndexError: 
               raise StopIteration
   def iter(lst): 
       if hasattr(lst,'__iter__'):
           return lst.__iter__()
       else:
           return _ListIterator(lst)

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
