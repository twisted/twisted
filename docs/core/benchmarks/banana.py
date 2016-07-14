#!/usr/bin/python
from __future__ import print_function

from timer import timeit
from twisted.spread.banana import b1282int

ITERATIONS = 100000

for length in (1, 5, 10, 50, 100):
    elapsed = timeit(b1282int, ITERATIONS, "\xff" * length)
    print("b1282int %3d byte string: %10d cps" % (length, ITERATIONS / elapsed))
