
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
