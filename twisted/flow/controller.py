# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
# Author: Clark Evans
# 

"""
flow.controller

This implements the various flow controllers, that is, those things which run
the flow stack.
"""

from base import *
from wrap import wrap
from twisted.internet import defer

class Block(Controller,Stage):
    """
    A controller which blocks on Cooperate events

    This converts a Stage into an iterable which can be used directly in python
    for loops and other iteratable constructs.  It does this by eating any
    Cooperate values and sleeping.  This is largely helpful for testing or
    within a threaded environment.  It converts other stages into one which
    does not emit cooperate events, ie::

        [1,2, Cooperate(), 3] => [1,2,3]
    """
    def __init__(self, stage, *trap):
        Stage.__init__(self)
        self._stage = wrap(stage,*trap)
        self.block = time.sleep

    def next(self):
        """ fetch the next value from the Stage flow """
        stage = self._stage
        while True:
            result = stage._yield()
            if result:
                if isinstance(result, Cooperate):
                    if result.__class__ == Cooperate:
                        self.block(result.timeout)
                        continue
                raise Unsupported(result)
            return stage.next()

class Deferred(Controller, defer.Deferred):
    """
    wraps up a Stage with a Deferred interface

    In this version, the results of the Stage are used to construct a list of
    results and then sent to deferred.  Further, in this version Cooperate is
    implemented via reactor's callLater.

    For example::

        from twisted.internet import reactor
        from twisted.flow import flow

        def res(x): print x
        d = flow.Deferred([1,2,3])
        d.addCallback(res)
        reactor.iterate()
    """
    def __init__(self, stage, *trap):
        defer.Deferred.__init__(self)
        self._results = []
        self._stage = wrap(stage, *trap)
        self._execute()

    def results(self, results):
        self._results.extend(results)

    def _execute(self, dummy = None):
        cmd = self._stage
        while True:
            result = cmd._yield()
            if cmd.results:
                self.results(cmd.results)
                cmd.results = []
            if cmd.stop:
                if not self.called:
                    self.callback(self._results)
                return
            if cmd.failure:
                cmd.stop = True
                if cmd._trap:
                    error = cmd.failure.check(*cmd._trap)
                    if error:
                        self._results.append(error)
                        continue
                self.errback(cmd.failure)
                return
            if result:
                if isinstance(result, CallLater):
                    result.callLater(self._execute)
                    return
                raise Unsupported(result)

