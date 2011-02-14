#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.internet import defer
from twisted.python import failure, util

"""
Now we see how an errback can handle errors. if an errback
does not raise an exception, the next callback in the chain 
will be called.
"""

class Counter(object):
    num = 0


def handleFailure(f):
    print "errback"
    print "we got an exception: %s" % (f.getTraceback(),)
    f.trap(RuntimeError)
    return "okay, continue on"

def handleResult(result):
    Counter.num += 1
    print "callback %s" % (Counter.num,)
    print "\tgot result: %s" % (result,)
    return "yay! handleResult was successful!"

def failAtHandlingResult(result):
    Counter.num += 1
    print "callback %s" % (Counter.num,)
    print "\tgot result: %s" % (result,)
    print "\tabout to raise exception"
    raise RuntimeError, "whoops! we encountered an error"

def callbackAfterErrback(result):
    Counter.num += 1
    print "callback %s" % (Counter.num,)
    print "\tgot result: %s" % (result,)
    


def behindTheScenes(result):
    # equivalent to d.callback(result)

    if not isinstance(result, failure.Failure): # ---- callback 
        try:
            result = handleResult(result)
        except:
            result = failure.Failure()
    else:                                       # ---- errback
        pass


    if not isinstance(result, failure.Failure): # ---- callback
        try:
            result = failAtHandlingResult(result)
        except:
            result = failure.Failure()
    else:                                       # ---- errback
        pass


    if not isinstance(result, failure.Failure): # ---- callback
        pass
    else:                                       # ---- errback
        try:
            result = handleFailure(result)
        except:
            result = failure.Failure()


    if not isinstance(result, failure.Failure): # ---- callback 
        try:
            result = callbackAfterErrback(result)
        except:
            result = failure.Failure()
    else:                                       # ---- errback
        pass



def deferredExample():
    d = defer.Deferred()
    d.addCallback(handleResult)
    d.addCallback(failAtHandlingResult)
    d.addErrback(handleFailure)
    d.addCallback(callbackAfterErrback)

    d.callback("success")


if __name__ == '__main__':
    behindTheScenes("success")
    print "\n-------------------------------------------------\n"
    Counter.num = 0
    deferredExample()

