#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.internet import defer
from twisted.python import failure, util

"""
Now comes the more nuanced addCallbacks, which allows us to make a
yes/no (branching) decision based on whether the result at a given point is
a failure or not.

here, we return the failure from noDecisionPassthru, the errback argument to
the first addCallbacks method invocation, and see what happens.
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

def yesDecision(result):
    Counter.num += 1
    print "yes decision %s" % (Counter.num,)
    print "\twasn't a failure, so we can plow ahead"
    return "go ahead!"

def noDecision(result):
    Counter.num += 1
    result.trap(RuntimeError)
    print "no decision %s" % (Counter.num,)
    print "\t*doh*! a failure! quick! damage control!"
    return "damage control successful!"
    
def noDecisionPassthru(result):
    Counter.num += 1
    print "no decision %s" % (Counter.num,)
    print "\t*doh*! a failure! don't know what to do, returning failure!"
    return result
    

def behindTheScenes(result):

    if not isinstance(result, failure.Failure): # ---- callback
        try:
            result = failAtHandlingResult(result)
        except:
            result = failure.Failure()
    else:                                       # ---- errback
        pass
    

    # this is equivalent to addCallbacks(yesDecision, noDecision)

    if not isinstance(result, failure.Failure): # ---- callback 
        try:
            result = yesDecision(result)
        except:
            result = failure.Failure()
    else:                                       # ---- errback
        try:
            result = noDecisionPassthru(result)
        except:
            result = failure.Failure()

    
    if not isinstance(result, failure.Failure): # ---- callback
        try:
            result = handleResult(result)
        except:
            result = failure.Failure()
    else:                                       # ---- errback
        pass


    # this is equivalent to addCallbacks(yesDecision, noDecision)

    if not isinstance(result, failure.Failure): # ---- callback 
        try:
            result = yesDecision(result)
        except:
            result = failure.Failure()
    else:                                       # ---- errback
        try:
            result = noDecision(result)
        except:
            result = failure.Failure()


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

    # noDecisionPassthru will be called
    d.addCallbacks(yesDecision, noDecisionPassthru) 
    d.addCallback(handleResult) # - A -

    # noDecision will be called
    d.addCallbacks(yesDecision, noDecision) 
    d.addCallback(handleResult) # - B - 
    d.addErrback(handleFailure)

    d.callback("success")


if __name__ == '__main__':
    behindTheScenes("success")
    print "\n-------------------------------------------------\n"
    Counter.num = 0
    deferredExample()

