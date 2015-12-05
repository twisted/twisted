# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

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
