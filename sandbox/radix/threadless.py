# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2003 Matthew W. Lefkowitz
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

"""
Threadless, a concurrency system for Twisted, built on Stackless Python.

This module requires Stackless Python 3.0. See http://stackless.com/
"""


# THIS is how the threadless reactor works.

# Any time the reactor makes a call to "user" code, it calls a special
# method to do it, callInTasklet.

# This method creates a new tasklet and channel associated with the
# method. Now, that doesn't mean that the method is run concurrently
# with the rest of the reactor: The user-function is still called
# synchronously. Associating the task with it just gives it a way to
# switch _back_ to the reactor when it needs to "block".

# In the future, I may optimize this so that each connection gets its
# own tasklet which is re-used for all user-functions associated with
# it. Although this may not be possible.

import new, types
import stackless


from twisted.python import failure, log

def makeContinuation(channel):
    from twisted.internet import reactor
    def continuation(result):
        reactor.callLater(0, channel.send, result)
    return continuation

def handleResult(result):
    if isinstance(result, Exception):
        raise result
    elif isinstance(result, failure.Failure):
        if result.tb:
            raise result.value.__class__, \
                  result.value, result.tb
        raise result.value
    else:
        return result


def takesContinuation(func):
    """
    Do this:

        def myFunc(cont):
            reactor.callLater(5, cont, None)
        myFunc = takesContinuation(myFunc)
        myFunc() #blocks for 5 seconds

    That is, `cont' will automagically be passed as the first argument
    to the function.

    `cont' should be called with a single argument. The argument will
    be the return value of myFunc.

    The resultant function will NOT RETURN until the continuation that
    is passed to it is called. Also, its `real' return value is
    ignored, and the one given to the continuation will be returned.
    """
    # If it's an _unbound_ method, we need to handle `self' specially,
    # because I want `self' to always be the first argument.

    # Stupid Python doesn't have distinct "Bound" and "Unbound" types,
    # so we check if im_self is None.

    if isinstance(func, types.MethodType) and func.im_self is None:
        def doIt(self, *args, **kwargs):
            channel = theScheduler.getChannel()
            continuation = makeContinuation(channel)
            func(self, continuation, *args, **kwargs)
            r = channel.receive()
            return handleResult(r)
    else:
        def doIt(*args, **kwargs):
            channel = theScheduler.getChannel()
            continuation = makeContinuation(channel)
            func(continuation, *args, **kwargs)
            r = channel.receive()
            return handleResult(r)

    return doIt

    # the new.function thing is broken, see
    # http://sourceforge.net/tracker/?group_id=5470&atid=105470&func=detail&aid=692776

    # XXX when stackless gets up to 2.2.3, (or more likely 2.3),
    # remove `return doIt' from above

    # using new.function here so our returned function will actually
    # have func's name (and type signature, incidentally), not "doIt"
    argdef = func.func_defaults
    nfsig = (doIt.func_code, globals(), func.__name__)
    if argdef:
        nfsig += (argdef,)
    r = new.function(*nfsig)
    return r


def blockOn(cont, deferred):
    """
    I am for calling 'legacy' functions that return Deferreds.

    New interfaces (that don't mind requiring Stackless) should use
    takesContinuation.
    """
    deferred.addBoth(cont)


blockOn = takesContinuation(blockOn)

class Scheduler:
    def __init__(self):
        self.taskletChannels = {} # mapping of tasklets to channels

    def _noReallyCallIt(self, f, *args, **kwargs):
        """
        I exist because there's no other way to know when the function
        has returned (as opposed to just blocking on a
        channel.receive())
        """
        t = stackless.getcurrent()
        
        self.taskletChannels[id(t)] = stackless.channel()
        try:
            try:
                f(*args, **kwargs)
            except:
                log.err()
        finally:
            del self.taskletChannels[id(t)]


    def callInTasklet(self, f, *args, **kwargs):
        t = stackless.tasklet(self._noReallyCallIt)(f, *args, **kwargs)
        t.run()


    def getChannel(self):
        """
        I am context-dependant.
        """
        return self.taskletChannels[id(stackless.getcurrent())]

theScheduler = Scheduler()



import time

from twisted.internet import default, main
from twisted.internet.defer import Deferred, DeferredList


class SelectReactor(default.SelectReactor):
    def mainLoop(self):
        while self.running:
            try:
                while self.running:
                    # Advance simulation time in delayed event
                    # processors.
                    theScheduler.callInTasklet(self.runUntilCurrent)
                    t2 = self.timeout()
                    t = self.running and t2
                    theScheduler.callInTasklet(self.doIteration, t)
            except:
                log.msg("Unexpected error in main loop.")
                log.deferr()
            else:
                log.msg('Main loop terminated.')


def install():
    from twisted.internet import main
    reactor = SelectReactor()
    main.installReactor(reactor)


