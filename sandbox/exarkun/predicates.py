# -*- coding: Latin-1 -*-

"""Predicates for the mini-language used by rresource.py"""

import struct
import socket
import time

def atoi(s):
    if s == '255.255.255.255':
        return -1
    return struct.unpack('!i', socket.inet_aton(s))[0]


class Address:
    def __eq__(self, address):
        return _Address(address, operator.eq)
    def __ne__(self, address):
        return _Address(address, operator.ne)


class _Address:
    subjugates = None

    def __init__(self, a, f):
        parts = a.split('/', 1)
        if len(parts) == 1:
            parts.append('255.255.255.255')
        self.host, self.mask = parts
        self.mask = atoi(self.mask)
        self.host = atoi(self.host) & self.mask
        self.f = f
    
    def check(self, resource, request):
        if self.f(atoi(request.client[1]) & self.mask, self.host):
            if self.subjugates is None:
                return True
            for s in self.subjugates:
                r = s.check(resource, request)
                if r is not None:
                    return r
        return None

    def __call__(self, *args):
        self.subjugates = args

class Tautology:
    def check(self, resource, request):
        if self.subjugates is not None:
            for s in self.subjugates:
                r = s.check(resource, request)
                if r is not None:
                    return r
            else:
                return None
        else:
            return True

    def __call__(self, *args):
        self.subjugates = args

class Contradiction:
    def check(self, resource, request):
        return False

    def __call__(self, *args):
        pass

import operator
tmpl = "def __%s__(self, m): return __DateThing(self.attr, m, operator.%s)"
class DateThing:
    def __init__(self, attr):
        self.attr = attr
    for fn in 'eq', 'ne', 'lt', 'gt', 'le', 'ge':
        exec tmpl % (fn, fn)

class _DateThing(Tautology):
    def __init__(self, a, m, f):
        self.a = a
        self.m = m
        self.f = f

    def check(self, resource, request):
        if self.f(getattr(time.localtime(), self.a), self.m):
            return Tautology.check(resource, request)
        return false

Month = DateThing('tm_mon')
MonthDay = DateThing('tm_mday')

tmpl = 'def __%s__(self, n): return _UniqueHosts(n, operator.%s)'
class UniqueHosts:
    for fn in 'eq', 'ne', 'lt', 'gt', 'le', 'ge':
        exec tmpl % (fn, fn)

class _UniqueHosts(Tautology):
    def __init__(self, n, op):
        self.n = n
        self.op = op
    
    def check(self, resource, request):
        i = 0
        d = {}
        for conn in request.channel.factory.connections:
            if conn.transport.getPeer()[1] not in d:
                d[conn.transport.getPeer()[1]] = None
                i += 1
        if self.op(i, self.n):
            return Tautology.check(self, resource, request)
        return False

tmpl = 'def __%s__(self, c): return _Connections(c, operator.%s)'
class Connections:
    for fn in 'eq', 'ne', 'lt', 'gt', 'le', 'ge':
        exec tmpl % (fn, fn)

class _Connections(Tautology):
    def __init__(self, c, op):
        self.c = c
        self.op = op
    
    def check(self, resource, request):
        if self.op(len(request.channel.factory.connections), self.c):
            return Tautology.check(self, resource, request)
        return False

Tautology = Tautology()
Contradiction = Contradiction()
Address = Address()
Connections = Connections()
UniqueHosts = UniqueHosts()

