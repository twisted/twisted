# -*- test-case-name: twisted.test.test_spread -*-

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

"""Utility classes for spread."""

from twisted.internet import defer
from twisted.python.failure import Failure


class LocalMethod:
    def __init__(self, local, name):
        self.local = local
        self.name = name

    def __call__(self, *args, **kw):
        return apply(self.local.callRemote, (self.name,)+args, kw)


class LocalAsRemote:
    """
    A class useful for emulating the effects of remote behavior locally.
    """
    reportAllTracebacks = 1
    def callRemote(self, name, *args, **kw):
        """Call a specially-designated local method.

        self.callRemote('x') will first try to invoke a method named
        sync_x and return its result (which should probably be a
        Deferred).  Second, it will look for a method called async_x,
        which will be called and then have its result (or Failure)
        automatically wrapped in a Deferred.
        """
        if hasattr(self, 'sync_'+name):
            return apply(getattr(self, 'sync_'+name), args, kw)
        try:
            method = getattr(self, "async_" + name)
            return defer.succeed(apply(method, args, kw))
        except:
            f = Failure()
            if self.reportAllTracebacks:
                f.printTraceback()
            return defer.fail(f)

    def remoteMethod(self, name):
        return LocalMethod(self, name)

from twisted.python.components import Interface, implements
from twisted.python.reflect import prefixedMethodNames

class LocalAsyncForwarder:
    """A class useful for forwarding a locally-defined interface.
    """

    def __init__(self, forwarded, interfaceClass, failWhenNotImplemented=0):
        assert implements(forwarded, interfaceClass)
        self.forwarded = forwarded
        self.interfaceClass = interfaceClass
        self.failWhenNotImplemented = failWhenNotImplemented

    def _callMethod(self, method, *args, **kw):
        return apply(getattr(self.forwarded, method), args, kw)

    def callRemote(self, method, *args, **kw):
        if hasattr(self.interfaceClass, method):
            result = apply(defer.execute, (self._callMethod,method)+args, kw)
            return result
        elif self.failWhenNotImplemented:
            return defer.fail(
                Failure(NotImplementedError,
                        "No Such Method in Interface: %s" % method))
        else:
            return defer.succeed(None)


class Pager:
    """I am an object which pages out information.
    """
    def __init__(self, collector):
        """Create a pager with a Reference to a remote collector.
        """
        self._stillPaging = 1
        self.collector = collector
        collector.broker.registerPageProducer(self)

    def stillPaging(self):
        """(internal) Method called by Broker.
        """
        if not self._stillPaging:
            self.collector.callRemote("endedPaging")
        return self._stillPaging

    def sendNextPage(self):
        """(internal) Method called by Broker.
        """
        self.collector.callRemote("gotPage", self.nextPage())

    def nextPage(self):
        """Override this to return an object to be sent to my collector.
        """
        raise NotImplementedError()
    
    def stopPaging(self):
        """Call this when you're done paging.
        """
        self._stillPaging = 0

class StringPager(Pager):
    """A simple pager that splits a string into chunks.
    """
    def __init__(self, collector, st, chunkSize=8192):
        self.string = st
        self.pointer = 0
        self.chunkSize = chunkSize
        Pager.__init__(self, collector)

    def nextPage(self):
        val = self.string[self.pointer:self.pointer+self.chunkSize]
        self.pointer += self.chunkSize
        if self.pointer >= len(self.string):
            self.stopPaging()
        return val

### Utility paging stuff.
from twisted.spread import pb
class CallbackPageCollector(pb.Referenceable):

    def __init__(self, callback):
        self.pages = []
        self.callback = callback
    def remote_gotPage(self, page):
        self.pages.append(page)
    def remote_endedPaging(self):
        self.callback(self.pages)

def getAllPages(referenceable, methodName, *args, **kw):
    """A utility method that will call a remote method which expects a
    PageCollector as the first argument."""
    d = defer.Deferred()
    referenceable.callRemote(methodName, CallbackPageCollector(d.callback), *args, **kw)
    return d
