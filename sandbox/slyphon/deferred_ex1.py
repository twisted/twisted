#!/usr/bin/python2.3

from twisted.internet import defer
from twisted.python import failure, util

"""
here we have a slightly more involved case. The deferred is called back with a
result. the first callback returns a value, the second callback, however
raises an exception, which is handled by the errback.
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

def failAtHandlingResult(result):
    global num; num += 1
    print "callback %s" % (num,)
    print "\tgot result: %s" % (result,)
    print "\tabout to raise exception"
    raise RuntimeError, "whoops! we encountered an error"


def nonDeferredExample(result):
    # equivalent to d.callback(result)

    if not isinstance(result, failure.Failure): 
        try:
            result = handleResult(result)
        except:
            result = failure.Failure()
    else:
        pass


    if not isinstance(result, failure.Failure): 
        try:
            result = failAtHandlingResult(result)
        except:
            result = failure.Failure()
    else:
        pass


    if not isinstance(result, failure.Failure): 
        pass
    else:
        try:
            result = handleFailure(result)
        except:
            result = failure.Failure()


def deferredExample():
    d = defer.Deferred()
    d.addCallback(handleResult)
    d.addCallback(failAtHandlingResult)
    d.addErrback(handleFailure)

    d.callback("success")


if __name__ == '__main__':
    nonDeferredExample("success")
    print "\n-------------------------------------------------\n"
    global num; num = 0
    deferredExample()
