# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test for L{paste.deploy} integration.
"""

from twisted.trial.unittest import TestCase
from twisted.web.paste import serverFactory


class TestServerFactory(TestCase):
    """
    Tests for L{serverFactory}.
    """
