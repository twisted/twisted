# -*- test-case-name: twisted.trial.test.test_trial -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>

"""Remote reporting for Trial.

For reporting test results in a seperate process.
"""
from __future__ import nested_scopes, generators


from twisted.python import components, failure, reflect
from twisted.python.compat import adict
from twisted.spread import jelly
from twisted.trial import reporter, itrial
from twisted.python.reflect import qual, namedAny

import zope.interface as zi

import os, types
from zope.interface import implements

class JellyableTestMethod(jelly.Jellyable, jelly.Unjellyable):
    zi.implements(itrial.ITestMethod, jelly.IJellyable, jelly.IUnjellyable)

    def __init__(self, original):
        self.original = original

    def getStateFor(self, jellier):
        tm = self.original
        m = tm.method
        d = adict(name = qual(m).split('.')[-1],
                  klass = qual(m.im_class),
                  fullName = qual(m),
                  setUp = qual(m.im_class.setUp),
                  tearDown = qual(m.im_class.tearDown))

        for eqattr in ['module', 'timeout', 'runs', 'startTime',
                       'endTime', 'skip', 'todo', 'hasTbs',
                       'status', 'failures', 'errors', 'results']:
            d[eqattr] = getattr(tm, eqattr, None)

            if eqattr in ['failures', 'errors', 'results']:
                d[eqattr] = [f.cleanFailure() for f in d.get(eqattr, [])]
                    
        return d


    def setStateFor(self, unjellier, state):
        for k in ['klass', 'setUp', 'tearDown']:
            state[k] = namedAny(state[k])
        self.__dict__ = state
        

class RemoteReporter(reporter.Reporter):
    def start(self, expectedTests):
        pass

    def reportStart(self, method):
        pass

    def reportImportError(self, name, exc):
        pass

    def reportResults(self, method):
        pass

    def stop(self, suite):
        pass



