#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.internet import defer
from twisted.python import failure, util

"""
Here we have the simplest case, a single callback and a single errback.
"""

num = 0

def handleFailure(f):
    print "errback"
    print "we got an exception: %s" % (f.getTraceback(),)
    f.trap(RuntimeError)

def handleResult(result):
    global num; num += 1
    print "callback %s" % (num,)
    print "\tgot result: %s" % (result,)
    return "yay! handleResult was successful!"


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
        pass
    else:                                       # ---- errback
        try:
            result = handleFailure(result)
        except:
            result = failure.Failure()


def deferredExample():
    d = defer.Deferred()
    d.addCallback(handleResult)
    d.addErrback(handleFailure)

    d.callback("success")


if __name__ == '__main__':
    behindTheScenes("success")
    print "\n-------------------------------------------------\n"
    global num; num = 0
    deferredExample()
