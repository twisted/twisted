#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.internet import defer
from twisted.python import failure, util

"""
Now we'll see what happens when you use 'addBoth'.
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

def doThisNoMatterWhat(arg):
    Counter.num += 1
    print "both %s" % (Counter.num,)
    print "\tgot argument %r" % (arg,)
    print "\tdoing something very important"
    # we pass the argument we received to the next phase here
    return arg   



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


    # ---- this is equivalent to addBoth(doThisNoMatterWhat)

    if not isinstance(result, failure.Failure): 
        try:
            result = doThisNoMatterWhat(result)
        except:
            result = failure.Failure()
    else:
        try:
            result = doThisNoMatterWhat(result)
        except:
            result = failure.Failure()
        

    if not isinstance(result, failure.Failure): # ---- callback
        pass
    else:                                       # ---- errback
        try:
            result = handleFailure(result)
        except:
            result = failure.Failure()


def deferredExample():
    d = defer.Deferred()
    d.addCallback(handleResult)
    d.addCallback(failAtHandlingResult)
    d.addBoth(doThisNoMatterWhat)
    d.addErrback(handleFailure)

    d.callback("success")


if __name__ == '__main__':
    behindTheScenes("success")
    print "\n-------------------------------------------------\n"
    Counter.num = 0
    deferredExample()
