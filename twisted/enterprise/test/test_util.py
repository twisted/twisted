# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import datetime

from twisted.trial.unittest import TestCase

from twext.enterprise.util import parseSQLTimestamp



class TimestampTests(TestCase):
    """
    Tests for date-related functions.
    """

    def test_parseSQLTimestamp(self):
        """
        L{parseSQLTimestamp} parses the traditional SQL timestamp.
        """
        tests = (
            ("2012-04-04 12:34:56", datetime.datetime(2012, 4, 4, 12, 34, 56)),
            ("2012-12-31 01:01:01", datetime.datetime(2012, 12, 31, 1, 1, 1)),
        )

        for sqlStr, result in tests:
            self.assertEqual(parseSQLTimestamp(sqlStr), result)
