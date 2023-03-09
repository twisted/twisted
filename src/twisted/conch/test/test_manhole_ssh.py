from hamcrest import assert_that

from twisted.cred.portal import IRealm
from twisted.trial import unittest
from twisted.trial.test.matchers import provides

try:
    from twisted.conch.manhole_ssh import TerminalRealm
except ImportError:
    ssh = False
else:
    ssh = True


class TerminalRealmTests(unittest.TestCase):
    if not ssh:
        skip = "cannot import t.conch.manhole_ssh (cryptography requirements missing?)"

    def test_TerminalRealm_implements_IRealm(self) -> None:
        """Regression test for #11812."""
        assert_that(TerminalRealm(), provides(IRealm))
