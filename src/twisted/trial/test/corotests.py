# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for coroutine handling by L{twisted.trial.unittest.TestCase}.
"""

from .detests import DeferredTests



class CoroutineTests(DeferredTests):
    """
    Tests for coroutine handling by L{twisted.trial.unittest.TestCase}.

    @note: These tests need to have parity with
    L{twisted.trial.unittest.test.detests.DeferredTests} insofar as we expect
    equivalent async implementations of the same tests to work,
    with the exception of deferred generators and inline callbacks, which use
    generators, which cannot co-exist with coroutines because Python.
    But that's OK, because coroutines replace inline callbacks, which replace
    deferred generators, so it's all good.
    """

    touched = False


    def error(self, reason):
        raise RuntimeError(reason)


    def touchClass(self, ignored):
        self.__class__.touched = True


    def setUp(self):
        self.__class__.touched = False


    async def test_pass(self):
        return "success"


    def test_passGenerated(self):
        raise NotImplementedError("Not applicable to coroutines")


    def test_passGenerated(self):
        raise NotImplementedError("Not applicable to coroutines")


    async def test_fail(self):
        raise self.failureException("I fail")


    async def test_failureInCallback(self):
        await self._cb_fail("fail")


    async def test_errorInCallback(self):
        await self._cd_error("error")


    async def test_skip(self):
        await self._cb_skip("skip")
        self.touchClass()


    async def test_thread(self):
        return await threads.deferToThread(lambda : None)


    async def test_expectedFailure(self):
        await self._cb_error("todo")

    test_expectedFailure.todo = "Expected failure"
