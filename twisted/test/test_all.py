
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
Amalgamate all Twisted testcases
"""

import test_reality
import test_observable
import test_reflect
import test_delay
import test_hook
import test_protocols
import test_smtp
import test_pop3
import test_dirdbm
import test_jelly
import test_import
import test_pb
import test_todo
import test_explorer
import test_banana
import test_rebuild
import test_toc
import test_words
import test_persisted
import test_pureber

from pyunit import unittest


def makeBigSuite(testCaseClasses, prefix='test'):
    cases = []
    for testCaseClass in testCaseClasses:
        cases = cases + map(testCaseClass,
                            unittest.getTestCaseNames(testCaseClass,
                                                      prefix,cmp))
    return unittest.TestSuite(cases)


def testSuite():
    cases = (test_observable.testCases + test_reality.testCases    +
             test_reflect.testCases    + test_delay.testCases      +
             test_hook.testCases       + test_protocols.testCases  +
             test_dirdbm.testCases     + test_jelly.testCases      +
             test_pb.testCases         + test_todo.testCases       +
             test_explorer.testCases   + test_banana.testCases     +
             test_rebuild.testCases    + test_toc.testCases        +
             test_smtp.testCases       + test_pop3.testCases       +
             test_words.testCases      + test_persisted.testCases  +
             test_pureber.testCases    +
             # Leave this one at the end.
             test_import.testCases)
    return makeBigSuite(cases)
