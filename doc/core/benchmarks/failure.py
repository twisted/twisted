
"""See how slow failure creation is"""

import random
from twisted.python import failure

random.seed(10050)
O = [0, 20, 40, 60, 80, 10, 30, 50, 70, 90]
DEPTH = 30

def pickVal():
    return random.choice([None, 1, 'Hello', [], {1: 1}, (1, 2, 3)])

def makeLocals(n):
    return ';'.join(['x%d = %s' % (i, pickVal()) for i in range(n)])

for nLocals in O:
    for i in range(DEPTH):
        s = """
def deepFailure%d_%d():
    %s
    deepFailure%d_%d()
""" % (nLocals, i, makeLocals(nLocals), nLocals, i + 1)
    exec s

    exec """
def deepFailure%d_%d():
    1 / 0
""" % (nLocals, DEPTH)

R = range(5000)
def fail(n):
    for i in R:
        try:
            eval('deepFailure%d_0' % n)()
        except:
            failure.Failure()

def fail_str(n):
    for i in R:
        try:
            eval('deepFailure%d_0' % n)()
        except:
            str(failure.Failure())

class PythonException(Exception): pass

def fail_easy(n):
    for i in R:
        try:
            failure.Failure(PythonException())
        except:
            pass

from timer import timeit
# for i in O:
#     timeit(fail, 1, i)

# for i in O:
#     print 'easy failing', i, timeit(fail_easy, 1, i)

for i in O:
    print 'failing', i, timeit(fail, 1, i)

# for i in O:
#     print 'string failing', i, timeit(fail_str, 1, i)
