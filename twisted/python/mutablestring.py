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
import string

class MutableString:
    def __init__(self, s=""):
        self.data=[]
        self.append(s)

    def __cmp__(self, other):
        return cmp(str(self), other)

    def __nonzero__(self):
        return not not (self.data and filter(lambda x: x, self.data))

    def __repr__(self):
        return self.__class__.__name__+'('+repr(str(self))+')'

    def __str__(self):
        s=string.join(map(lambda x: str(x), self.data), '')
        self.data=[]
        self.append(s)
        return s

    def __len__(self):
        l=0
        for i in self.data:
            l=l+len(i)
        return l

    def __getitem__(self, key):
        if key<0:
            key=key+len(self)
            if key<0:
                raise IndexError, "MutableString index out of range"
        for s in self.data:
            if key<len(s):
                return s[key]
            key=key-len(s)
        raise IndexError, "MutableString index out of range"

    def __setitem__(self, key, value):
        if key<0:
            key=key+len(self)
            if key<0:
                raise IndexError, "MutableString index out of range"
        for i in range(0, len(self.data)):
            if key<len(self.data[i]):
                self.data[i:i+1]=[self.data[i][:key],
                                  value,
                                  self.data[i][key+1:]]
                return i[key]
            key=key-len(self.data[i])
        raise IndexError, "MutableString index out of range"

    def __delitem__(self, key):
        if key<0:
            key=key+len(self)
            if key<0:
                raise IndexError, "MutableString index out of range"
        for i in range(0, len(self.data)):
            if key<len(self.data[i]):
                self.data[i:i+1]=[self.data[i][:key],
                                  self.data[i][key+1:]]
                return
            key=key-len(self.data[i])
        raise IndexError, "MutableString index out of range"

    def __getslice__(self, i, j):
        r=MutableString()
        if i<0:
            i=i+len(self)
            if i<0:
                i=0
        if j<0:
            j=j+len(self)
            if j<0:
                j=0

        if i>=j:
            return r

        x=0
        while x<len(self.data) and i>=len(self.data[x]):
            i=i-len(self.data[x])
            j=j-len(self.data[x])
            x=x+1

        if x>=len(self.data):
            return r

        r.append(self.data[x][i:j])
        while j>len(self.data[x]):
            j=j-len(self.data[x])
            x=x+1
            if x>=len(self.data):
                return r
            r.append(self.data[x][0:j])
        return r

    def __setslice__(self, i, j, s):
        r=MutableString()
        r.append(self[:i])
        r.append(s)
        r.append(self[j:])
        self.set(r)

    def __delslice__(self, i, j):
        r=MutableString()
        r.append(self[:i])
        r.append(self[j:])
        self.set(r)

    def append(self, s):
        x=str(s)
        if x:
            self.data.append(x)

    def set(self, s):
        self.data=[]
        self.append(s)

    def __add__(self, other):
        return str(self)+other

    def __mul__(self, other):
        return str(self)*other

    def __radd__(self, other):
        return other+str(self)

    def __rmul__(self, other):
        return other*str(self)

    def __complex__(self):
        return complex(str(self))

    def __int__(self):
        return int(str(self))

    def __float__(self):
        return float(str(self))
