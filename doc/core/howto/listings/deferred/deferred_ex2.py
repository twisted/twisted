#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.internet import defer
from twisted.python import failure, util

"""
This example shows an important concept that many deferred newbies
(myself included) have trouble understanding. 

when an error occurs in a callback, the first errback after the error
occurs will be the next method called. (in the next example we'll
see what happens in the 'chain' after an errback).
"""

class Counter(object):
    num = 0

def handleFailure(f):
    print "errback"
    print "we got an exception: %s" % (f.getTraceback(),)
    f.trap(RuntimeError)

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



def behindTheScenes(result):
    # equivalent to d.callback(result)

    # now, let's make the error happen in the first callback
    
    if not isinstance(result, failure.Failure): # ---- callback
        try:
            result = failAtHandlingResult(result)
        except:
            result = failure.Failure()
    else:                                       # ---- errback
        pass


    # note: this callback will be skipped because
    # result is a failure

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
    d.addCallback(failAtHandlingResult)
    d.addCallback(handleResult)
    d.addErrback(handleFailure)

    d.callback("success")


if __name__ == '__main__':
    behindTheScenes("success")
    print "\n-------------------------------------------------\n"
    Counter.num = 0
    deferredExample()

