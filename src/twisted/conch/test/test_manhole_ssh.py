from hamcrest import assert_that

from twisted.conch.manhole_ssh import TerminalRealm
from twisted.cred.portal import IRealm
from twisted.trial import unittest
from twisted.trial.test.matchers import provides


class TerminalRealmTests(unittest.TestCase):
    def test_TerminalRealm_implements_IRealm(self) -> None:
        """Regression test for #11812."""
        assert_that(TerminalRealm(), provides(IRealm))
