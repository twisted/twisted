"""
Amalgamate all Twisted testcases
"""

import test_reality
import test_observable
import test_reflect
import test_delay
import test_hook
import test_protocols
#import test_smtp
#import test_pop3
import test_dirdbm
#import test_sexpy
import test_jelly
import test_import
import test_pb
import test_todo
import test_explorer
import test_banana
import test_rebuild
import test_toc
from pyunit import unittest


def makeBigSuite(testCaseClasses, prefix='test'):
    cases = []
    for testCaseClass in testCaseClasses:
        cases = cases + map(testCaseClass,
                            unittest.getTestCaseNames(testCaseClass,
                                                      prefix,cmp))
    return unittest.TestSuite(cases)


def testSuite():
    cases = (test_observable.testCases + test_reality.testCases   +
             test_reflect.testCases    + test_delay.testCases     +
             test_hook.testCases       + test_protocols.testCases +
             test_dirdbm.testCases     + test_jelly.testCases     +
             test_pb.testCases         + test_todo.testCases      +
             test_explorer.testCases   + test_banana.testCases    +
             test_rebuild.testCases    + test_toc.testCases       +
             # Leave this one at the end.
             test_import.testCases)
    return makeBigSuite(cases)
