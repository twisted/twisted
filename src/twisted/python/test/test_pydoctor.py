# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python._pydoctor}.
"""
from twisted.python.reflect import requireModule
from twisted.trial.unittest import TestCase

model = requireModule("pydoctor.model")
pydoctorSkip = None
TwistedSphinxInventory = object
TwistedSystem = object
if model is None:
    pydoctorSkip = "Pydoctor is not present."
else:
    # We have a valid pydoctor.
    from twisted.python._pydoctor import TwistedSphinxInventory, TwistedSystem


class TwistedSystemTests(TestCase):
    """
    Tests for L{TwistedSystem}.
    """

    skip = pydoctorSkip

    def test_initCustomSphinxInventory(self):
        """
        After initialization it has a custom C{intersphinx} member.
        """
        sut = TwistedSystem()

        self.assertIsInstance(sut.intersphinx, TwistedSphinxInventory)

class TwistedSphinxInventoryTests(TestCase):
    """
    Tests for L{TwistedSphinxInventory}.
    """

    skip = pydoctorSkip

    def getInventoryWithZope(self):
        """
        Initialized a pre-loaded inventory.

        @return: A new inventory which already has a few I{zope.interface}
            inter sphinx links loaded.
        @rtype: L{TwistedSphinxInventory}
        """
        inventory = TwistedSphinxInventory(logger=object(), project_name="Super Duper")

        zopeBaseURL = "https://zope.tld"
        zopeAPIURL = "api.html#$"
        inventory._links.update(
            {
                "zope.interface.interfaces.IInterface": (zopeBaseURL, zopeAPIURL),
                "zope.interface.declarations.implementer": (zopeBaseURL, zopeAPIURL),
            }
        )

        return inventory

    def test_getLinkExistentInInterSphinx(self):
        """
        Return the full URL based on pre-loaded inter sphinx objects.
        """
        sut = self.getInventoryWithZope()

        result = sut.getLink("zope.interface.interfaces.IInterface")

        self.assertEqual(
            "https://zope.tld/api.html#zope.interface.interfaces.IInterface", result
        )

    def test_getLinkZopeNonExistent(self):
        """
        Any reference to I{zope.interface} which is not in the inter sphinx
        database returns L{None}.
        """
        sut = self.getInventoryWithZope()

        # Interface is at zope.interface.interfaces.IInterface so using the
        # short name will fail to find the url.
        result = sut.getLink("zope.interface.Interface")
        self.assertIsNone(result)
        # Any unknown reference returns None.
        result = sut.getLink("zope.interface.NoSuchReference")
        self.assertIsNone(result)

    def test_getLinkZopeAdapterRegistry(self):
        """
        I{zope.interface.adapter.AdapterRegistry} is a special case for which
        the link the narrative docs is returned as there is no API docs yet.
        """
        sut = self.getInventoryWithZope()

        result = sut.getLink("zope.interface.adapter.AdapterRegistry")

        self.assertEqual("https://zope.tld/adapter.html", result)
