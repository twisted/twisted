
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


# System Imports
import traceback
from cStringIO import StringIO

# Twisted Imports
from twisted.python import log

class Deferred:
    """This is a callback which will be put off until later.
    """

    armed = 0
    called = 0

    def __init__(self):
        self.callbacks = []

    def addCallbacks(self, callback, errback,
                     callbackArgs=None, callbackKeywords=None,
                     errbackArgs=None, errbackKeywords=None):
        """Add a pair of callbacks (success and error) to this Deferred.

        These will be executed when the 'master' callback is run.
        """
        self.callbacks.append(((callback, callbackArgs, callbackKeywords),
                              (errback, errbackArgs, errbackKeywords)))


    def callback(self, result):
        """The callback to register with whatever will be calling this Deferred.
        """
        self.runCallbacks(result, 0)


    def errback(self, error):
        """The error callback to register with whatever will be calling this Deferred.
        """
        self.runCallbacks(error, 1)


    def runCallbacks(self, result, isError):
        """Run all callbacks and/or errors that have been added to this Deferred.

        Each callback will have its result passed as the first argument to the
        next; this way, the callbacks act as a 'processing chain'.

        If this deferred has not been armed yet, nothing will happen.
        """
        self.called = isError + 1
        if self.armed:
            for item in self.callbacks:
                callback, args, kw = item[isError]
                args = args or ()
                kw = kw or {}
                try:
                    # print callback, result, args, kw
                    result = apply(callback, (result,)+args, kw)
                except:
                    io = StringIO()
                    traceback.print_exc(file=io)
                    gv = io.getvalue()
                    print gv
                    result = gv
                    isError = 1
        else:
            self.cbResult = result

    def arm(self):
        """State that this function is ready to be called.

        This is to prevent callbacks from being executed sometimes
        synchronously and sometimes asynchronously.  The system expecting a
        Delayed will explicitly arm the delayed after it has been returned; at
        _that_ point, it may fire later.
        """
        if not self.armed:
            self.armed = 1
            if self.called:
                self.runCallbacks(self.cbResult, self.called - 1)
        else:
            log.msg("WARNING: double-arming deferred.")


__all__ = ["Deferred"]
