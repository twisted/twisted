# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import pytest

from twisted.internet import reactor
from twisted.internet.defer import Deferred, succeed
from twisted.trial.reporter import TestResult
from twisted.trial.unittest import TestCase


class BenchmarkMixin:
    def testPlain(self):
        pass

    def testResolvedDeferred(self):
        return succeed(None)

    def testUnresolvedDeferred(self):
        d = Deferred()
        reactor.callLater(0, d.callback, None)
        return d

    def testAddCleanupPlain(self):
        self.addCleanup(lambda: None)

    def testAddCleanupResolvedDeferred(self):
        self.addCleanup(lambda: succeed(None))

    def testAddCleanupUnresolvedDeferred(self):
        def cleanup():
            d = Deferred()
            reactor.callLater(0, d.callback, None)
            return d

        self.addCleanup(cleanup)


class BenchmarkTestsNoSetUp(BenchmarkMixin, TestCase):
    pass


class BenchmarkTestsSetUpTearDownPlain(BenchmarkMixin, TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass


class BenchmarkTestsSetUpTearDownResolvedDeferred(BenchmarkMixin, TestCase):
    def setUp(self):
        return succeed(None)

    def tearDown(self):
        return succeed(None)


class BenchmarkTestsSetUpTearDownUnresolvedDeferred(BenchmarkMixin, TestCase):
    def setUp(self):
        d = Deferred()
        reactor.callLater(0, d.callback, None)
        return d

    def tearDown(self):
        d = Deferred()
        reactor.callLater(0, d.callback, None)
        return d


@pytest.mark.parametrize(
    "method_name",
    [
        "testPlain",
        "testResolvedDeferred",
        "testUnresolvedDeferred",
        "testAddCleanupPlain",
        "testAddCleanupResolvedDeferred",
        "testAddCleanupUnresolvedDeferred",
    ],
)
def test_main_method(benchmark, method_name):
    """Measure the speed of tests with different implementations of test method"""

    def go():
        result = TestResult()
        BenchmarkTestsNoSetUp(method_name).run(result)

    benchmark(go)


@pytest.mark.parametrize(
    "test_class",
    [
        BenchmarkTestsSetUpTearDownPlain,
        BenchmarkTestsSetUpTearDownResolvedDeferred,
        BenchmarkTestsSetUpTearDownUnresolvedDeferred,
    ],
)
def test_setup_teardown(benchmark, test_class):
    """Measure the speed of tests with different implementations of setUp and tearDown"""

    def go():
        result = TestResult()
        test_class("testPlain").run(result)

    benchmark(go)
