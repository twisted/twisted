# -*- test-case-name: twisted.pb.test.test_pb,twisted.pb.test.test_gift -*-

from zope.interface import implements
from twisted.internet import defer, reactor
from twisted.pb import pb, schema

class RIHelper(pb.RemoteInterface):
    def set(obj=schema.Any()): return bool
    def set2(obj1=schema.Any(), obj2=schema.Any()): return bool
    def append(obj=schema.Any()): return schema.Any()
    def get(): return schema.Any()
    def echo(obj=schema.Any()): return schema.Any()
    def defer(obj=schema.Any()): return schema.Any()
    def hang(): return schema.Any()

class HelperTarget(pb.Referenceable):
    implements(RIHelper)
    d = None
    def __init__(self, name="unnamed"):
        self.name = name
    def __repr__(self):
        return "<HelperTarget %s>" % self.name
    def waitfor(self):
        self.d = defer.Deferred()
        return self.d

    def remote_set(self, obj):
        self.obj = obj
        if self.d:
            self.d.callback(obj)
        return True
    def remote_set2(self, obj1, obj2):
        self.obj1 = obj1
        self.obj2 = obj2
        return True

    def remote_append(self, obj):
        self.calls.append(obj)

    def remote_get(self):
        return self.obj

    def remote_echo(self, obj):
        self.obj = obj
        return obj

    def remote_defer(self, obj):
        d = defer.Deferred()
        reactor.callLater(1, d.callback, obj)
        return d

    def remote_hang(self):
        self.d = defer.Deferred()
        return self.d

