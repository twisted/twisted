# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""PB interop server."""

from twisted.spread import pb, jelly, flavors
from twisted.internet import reactor


class Interop(pb.Root):
    """Test object for PB interop tests."""

    def __init__(self):
        self.o = pb.Referenceable()
    
    def remote_int(self):
        return 1

    def remote_string(self):
        return "string"

    def remote_unicode(self):
        return u"string"

    def remote_float(self):
        return 1.5

    def remote_list(self):
        return [1, 2, 3]

    def remote_recursive(self):
        l = []
        l.append(l)
        return l

    def remote_dict(self):
        return {1 : 2}

    def remote_reference(self):
        return self.o

    def remote_local(self, obj):
        d = obj.callRemote("hello")
        d.addCallback(self._local_success)

    def _local_success(self, result):
        if result != "hello, world":
            raise ValueError, "%r != %r" % (result, "hello, world")

    def remote_receive(self, obj):
        expected = [1, 1.5, "hi", u"hi", {1 : 2}]
        if obj != expected:
            raise ValueError, "%r != %r" % (obj, expected)

    def remote_self(self, obj):
        if obj != self:
            raise ValueError, "%r != %r" % (obj, self)

    def remote_copy(self, x):
        o = flavors.Copyable()
        o.x = x
        return o


if __name__ == '__main__':
    reactor.listenTCP(8789, pb.PBServerFactory(Interop()))
    reactor.run()



