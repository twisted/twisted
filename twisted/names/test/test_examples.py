# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.names} example scripts.
"""

from twisted.test.testutils import ExecutableExampleTestMixin
from twisted.trial.unittest import TestCase



class TestDnsTests(ExecutableExampleTestMixin, TestCase):
    """
    Test the testdns.py example script.
    """

    examplePath = 'doc/names/examples/testdns.py'



class GetHostByNameTests(ExecutableExampleTestMixin, TestCase):
    """
    Test the gethostbyname.py example script.
    """

    examplePath = 'doc/names/examples/gethostbyname.py'



class DnsServiceTests(ExecutableExampleTestMixin, TestCase):
    """
    Test the dns-service.py example script.
    """

    examplePath = 'doc/names/examples/dns-service.py'
