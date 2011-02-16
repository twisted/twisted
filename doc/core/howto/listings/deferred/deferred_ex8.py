#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.internet import defer
from twisted.python import failure, util


class Counter(object):
    num = 0
    let = 'a'

    def incrLet(cls):
        cls.let = chr(ord(cls.let) + 1)
    incrLet = classmethod(incrLet)
       

def handleFailure(f):
    print "errback"
    print "we got an exception: %s" % (f.getTraceback(),)
    return f

def subCb_B(result):
    print "sub-callback %s" % (Counter.let,)
    Counter.incrLet()
    s = " beautiful!"
    print "\tadding %r to result" % (s,)
    result += s
    return result

def subCb_A(result):
    print "sub-callback %s" % (Counter.let,)
    Counter.incrLet()
    s = " are "
    print "\tadding %r to result" % (s,)
    result += s
    return result

def mainCb_1(result):
    Counter.num += 1
    print "callback %s" % (Counter.num,)
    print "\tgot result: %s" % (result,)
    result += " Deferreds "

    d = defer.Deferred().addCallback(subCb_A
                       ).addCallback(subCb_B)
    d.callback(result)
    return d

def mainCb_2(result):
    Counter.num += 1
    print "callback %s" % (Counter.num,)
    print "\tgot result: %s" % (result,)
    

def deferredExample():
    d = defer.Deferred().addCallback(mainCb_1
                       ).addCallback(mainCb_2)

    d.callback("I hope you'll agree: ")


if __name__ == '__main__':
    deferredExample()

