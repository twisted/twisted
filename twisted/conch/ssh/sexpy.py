# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
#

def parse(s):
    s = s.strip()
    expr = []
    while s:
        if s[0] == '(':
            newSexp = []
            if expr:
                expr[-1].append(newSexp)
            expr.append(newSexp)
            s = s[1:]
            continue
        if s[0] == ')':
            aList = expr.pop()
            s=s[1:]
            if not expr:
                assert not s
                return aList
            continue
        i = 0
        while s[i].isdigit(): i+=1
        assert i
        length = int(s[:i])
        data = s[i+1:i+1+length]
        expr[-1].append(data)
        s=s[i+1+length:]
    assert 0, "this should not happen"

def pack(sexp):
    s = ""
    for o in sexp:
        if type(o) in (type(()), type([])):
            s+='('
            s+=pack(o)
            s+=')'
        else:
            s+='%i:%s' % (len(o), o)
    return s
