#!/usr/bin/python

from cStringIO import StringIO
from timer import timeit
from twisted.spread import banana, _banana

def dataReceived(cls, data):
    b = cls()
    b.setPrefixLimit(64)
    b.currentDialect = "pb"
    retval = []
    b.expressionReceived = lambda result: retval.append(result)
    b.dataReceived(data)
    return retval[0]

def encode(cls, data):
    b = cls()
    b.setPrefixLimit(64)
    b.currentDialect = "pb"
    b.expressionReceived = lambda ign: None
    s = StringIO()
    e = b._encode(data, s.write)
    v = s.getvalue()
    return v

ITERATIONS = 100000

for length in (1, 5, 10, 50, 100):
    elapsed = timeit(banana.b1282int, ITERATIONS, "\xff" * length)
    c_elapsed = timeit(_banana.b1282int, ITERATIONS, "\xff" * length)
    print "b1282int %3d byte string: py:%10d c:%10d cps" % \
            (length, ITERATIONS / elapsed, ITERATIONS / c_elapsed)

ITERATIONS = 10000
for length in (1, 5, 10, 50, 100):
    e = encode(banana.Banana, [(0,"\xff")] * length)
    elapsed = timeit(dataReceived, ITERATIONS, banana.Banana, e)
    c_elapsed = timeit(dataReceived, ITERATIONS, _banana.Banana, e)
    print "dataReceived %3d element list: py:%10d c:%10d cps" % \
            (length, ITERATIONS / elapsed, ITERATIONS / c_elapsed)
