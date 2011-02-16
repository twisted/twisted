#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.internet import defer
from twisted.python import failure, util

"""
The deferred callback chain is stateful, and can be executed before
or after all callbacks have been added to the chain
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

def deferredExample1():
    # this is another common idiom, since all add* methods
    # return the deferred instance, you can just chain your
    # calls to addCallback and addErrback

    d = defer.Deferred().addCallback(failAtHandlingResult
                       ).addCallback(handleResult
                       ).addErrback(handleFailure)

    d.callback("success")

def deferredExample2():
    d = defer.Deferred()

    d.callback("success")

    d.addCallback(failAtHandlingResult)
    d.addCallback(handleResult)
    d.addErrback(handleFailure)


if __name__ == '__main__':
    deferredExample1()
    print "\n-------------------------------------------------\n"
    Counter.num = 0
    deferredExample2()

