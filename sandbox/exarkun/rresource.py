from twisted.web import resource, error

# Relying on the socket module is vulgar.  Alas.
import socket
import struct
import time

class RestrictedResource(resource.Resource):
    default = True
    
    def __init__(self, wrapped, rules):
        resource.Resource.__init__(self)
        self.wrapped = wrapped
        self.rules = rules

    def getChild(self, name, request):
        if self.checkRequest(request):
            return self.wrapped.getChild(name, request)
        else:
            return error.ForbiddenResource("Access denied")

    def render(self, request):
        if self.checkRequest(request, self.rules):
            return self.wrapped.render(request)
        else:
            request.setResponseCode(403)
            return 'Access denied'

    def checkRequest(self, request, rules):
        for (condition, rule) in rules:
            if condition.check(self, request):
                try:
                    c = rule.check
                except AttributeError:
                    b = self.checkRequest(request, rule)
                else:
                    b = c(self, request)
                if b is not None:
                    return b
        return self.default

def atoi(s):
    return struct.unpack('!i', socket.inet_aton(s))[0]

class Rule:
    def __not__(self):
        return Negate(self)

class Tautology(Rule):
    def check(self, resource, request):
        return True

class Contradiction(Rule):
    def check(self, resource, request):
        return False

class Negate(Rule):
    def __init__(self, rule):
        self.rule = rule
    
    def __not__(self):
        return self.rule
    
    def check(self, resource, request):
        res = self.rule.check(resource, request)
        if res is None:
            return res
        return not res

class Address(Rule):
    def __init__(self, allowed = '127.0.0.1', netmask = '255.255.255.255'):
        self.allowed = atoi(allowed)
        self.netmask = atoi(netmask)

    def check(self, resource, request):
        if (atoi(request.client[1]) & self.netmask) == self.allowed:
            return True
        return False

class Connections(Rule):
    def __init__(self, max):
        self.maximum = max
    
    def check(self, resource, request):
        # This is kind of expensive, I suppose!
        i = 0
        for c in resource.requests:
            if c.client[1] == request.client[1]:
                i += 1
                if i > self.maximum:
                    return False
        return None

class UniqueHosts(Rule):
    def __init__(self, max):
        self.maximum = max
    
    def check(self, resource, request):
        i = 0
        d = {}
        for c in resource.requests:
            if c.client[1] not in d:
                d[c.clients[1]] = None
                i += 1
                if i > self.maximum:
                    return False
        return None

class Month(Rule):
    def __init__(self, which):
        self.which = which
    
    def check(self, resource, request):
        if self.which == time.localtime().tm_mon:
            return True
        return None

class MonthDay(Rule):
    def __init__(self, which):
        self.which = which
    
    def check(self, resource, request):
        if self.which == time.localtime().tm_mday:
            return True
        return None

def main():
    from twisted.web import server
    from twisted.web import static
    
    site = server.Site(RestrictedResource(
        static.File('.'), [(
            # Always let localhost connect
            Address('127.0.0.1', '255.255.255.255'),
            Tautology()
        ), (
            Month(10), [(
                MonthDay(29), [(
                    # Shut down the site for no good reason the
                    # day before halloween.
                    Tautology(),
                    Contradiction()
                )]), (
                MonthDay(30), [(
                    # We are busy on Halloween!  Deny our
                    # employees access when load starts to
                    # get high.
                    Address('10.0.0.0', '255.0.0.0'),
                    UniqueHosts(512)
                )]), (
                    # Also, allow only 5 connections per host
                    Tautology(),
                    Connections(5)
                )
            ]
        ), (
            # For the rest of the year, 10 connections per host
            Tautology(),
            Connections(10)
        )]
    ))
            
    # This structure could be represented with a new language expressed in
    # Python syntax:
    #
    # [
    #     (Address == '127.0.0.1/255.255.255.255')(Tautology),
    #     (Month == 10)(
    #         (MonthDay == 29)(Contradiction),
    #         (MonthDay == 30)(
    #             (Address == '10.0.0.0/255.0.0.0')(UniqueHosts <= 512)
    #         )
    #     ), (Tautology)(Connections <= 10)
    # ]
    #
    
class Address:
    def __eq__(self, address):
        return _Address(address)

class _Address:
    subjugates = None

    def __init__(self, a):
        parts = a.split('/', 1)
        if len(parts) == 1:
            parts.append('255.255.255.255')
        self.host, self.mask = parts
        self.host = atoi(self.host)
        self.mask = atoi(self.mask)
    
    def check(self, resource, request):
        if atoi(request.client[1]) & self.mask == self.host:
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
