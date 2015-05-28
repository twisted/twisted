# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twext.enterprise.fixtures}.

Quis custodiet ipsos custodes?  This module, that's who.
"""

from twext.enterprise.fixtures import buildConnectionPool

from twisted.trial.unittest import TestCase
from twisted.trial.reporter import TestResult
from twext.enterprise.adbapi2 import ConnectionPool



class PoolTests(TestCase):
    """
    Tests for fixtures that create a connection pool.
    """

    def test_buildConnectionPool(self):
        """
        L{buildConnectionPool} returns a L{ConnectionPool} which will be
        running only for the duration of the test.
        """
        collect = []

        class SampleTest(TestCase):
            def setUp(self):
                self.pool = buildConnectionPool(self)

            def test_sample(self):
                collect.append(self.pool.running)

            def tearDown(self):
                collect.append(self.pool.running)

        r = TestResult()
        t = SampleTest("test_sample")
        t.run(r)
        self.assertIsInstance(t.pool, ConnectionPool)
        self.assertEqual([True, False], collect)
