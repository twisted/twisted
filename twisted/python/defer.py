

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
import types
import sys
from cStringIO import StringIO

class AlreadyArmedError(Exception):
    pass

def logError(err):
    if isinstance(err, failure.Failure):
        err.printTraceback(log)
    else:
        log.msg(str(err))
    return err

def _sched(m):
    from twisted.internet import task
    task.schedule(m)

def succeed(result):
    d = Deferred()
    d.callback(result)
    _sched(d.arm)
    return d

def fail(result):
    d = Deferred()
    d.errback(result)
    _sched(d.arm)
    return d

class Deferred:
    """This is a callback which will be put off until later.
    """

    armed = 0
    #self.called: 0 = "not called"; 1 = "answered", 2 = "errored"
    called = 0
    default = 0

    def __init__(self):
        self.callbacks = []

    def addCallbacks(self, callback, errback=None,
                     callbackArgs=None, callbackKeywords=None,
                     errbackArgs=None, errbackKeywords=None, asDefaults=0):
        """Add a pair of callbacks (success and error) to this Deferred.

        These will be executed when the 'master' callback is run.
        """
        if self.armed:
            raise AlreadyArmedError("You cannot add callbacks after a deferred"
                                    "has already been armed.")
        cbs = ((callback, callbackArgs, callbackKeywords),
               (errback or logError, errbackArgs, errbackKeywords))
        if self.default:
            self.callbacks[-1] = cbs
        else:
            self.callbacks.append(cbs)
        self.default = asDefaults
        return self

    def addCallback(self, callback, *args, **kw):
        return self.addCallbacks(callback, callbackArgs=args, callbackKeywords = kw)

    def callback(self, result):
        """Run all success callbacks that have been added to this Deferred.

        Each callback will have its result passed as the first
        argument to the next; this way, the callbacks act as a
        'processing chain'.

        If this deferred has not been armed yet, nothing will happen.
        """
        self._runCallbacks(result, 0)
        return self


    def errback(self, error):
        """Run all error callbacks that have been added to this Deferred.

        Each callback will have its result passed as the first
        argument to the next; this way, the callbacks act as a
        'processing chain'.

        If this deferred has not been armed yet, nothing will happen.
        """
        self._runCallbacks(error, 1)
        return self


    def _runCallbacks(self, result, isError):
        self.called = isError + 1
        if self.armed:
            for item in self.callbacks:
                callback, args, kw = item[isError]
                args = args or ()
                kw = kw or {}
                try:
                    # print callback, result, args, kw
                    # print 'defres:',callback,result
                    result = apply(callback, (result,)+tuple(args), kw)
                    if isinstance(result, Deferred):
                        print callback, result
                        raise 'suck iet'
                    if type(result) != types.StringType:
                        # TODO: make this hack go away; it has something to do
                        # with PB returning strings from errbacks that are
                        # actually tracebacks that we still want to handle as
                        # errors sometimes... can't find exactly where right
                        # now
                        if not isinstance(result, failure.Failure):
                            isError = 0
                except:
                    result = failure.Failure()
                    isError = 1
                    # if this was the last pair of callbacks, we must make sure
                    # that the error was logged, otherwise we'll never hear about it.
                    if item == self.callbacks[-1]:
                        logError(result)
        else:
            self.cbResult = result


    def arm(self):
        #start doing callbacks whenever you're ready, Mr. Deferred.
        """State that this function is ready to be called.

        This is to prevent callbacks from being executed sometimes
        synchronously and sometimes asynchronously.  The system
        expecting a Deferred will explicitly arm the delayed after
        it has been returned; at _that_ point, it may fire later.
        """
        if not self.armed:
            self.armed = 1
            if self.called:
                #'self.called - 1' is so self.called won't be changed.
                self._runCallbacks(self.cbResult, self.called - 1)
##        else:
##            log.msg("WARNING: double-arming deferred.")


__all__ = ["Deferred", "succeed", "fail"]

# Sibling Imports
import log
import failure

