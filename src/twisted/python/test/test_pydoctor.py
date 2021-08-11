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

    def test_privacyClassBaseTestPackage(self):
        """
        The base I{twisted.test} package is visible to allow traversal to a
        few selected test API which is visible.
        """
        sut = TwistedSystem()
        twistedPackage = model.Package(
            system=sut,
            name="twisted",
            parent=None,
        )
        twistedTestPackage = model.Package(
            system=sut,
            name="test",
            parent=twistedPackage,
        )

        result = sut.privacyClass(twistedTestPackage)

        self.assertIs(result, model.PrivacyClass.VISIBLE)

    def test_privacyClassProtoHelpers(self):
        """
        The I{twisted.test.proto_helpers} module is visible.
        """
        sut = TwistedSystem()
        twistedPackage = model.Package(
            system=sut,
            name="twisted",
            parent=None,
        )
        twistedTestPackage = model.Package(
            system=sut,
            name="test",
            parent=twistedPackage,
        )
        twistedProtoHelpersModule = model.Module(
            system=sut,
            name="proto_helpers",
            parent=twistedTestPackage,
        )

        result = sut.privacyClass(twistedProtoHelpersModule)

        self.assertIs(result, model.PrivacyClass.VISIBLE)

    def test_privacyClassChildTestModule(self):
        """
        Any child of the I{twisted.test} package is hidden.
        """
        sut = TwistedSystem()
        twistedPackage = model.Package(
            system=sut,
            name="twisted",
            parent=None,
        )
        twistedTestPackage = model.Package(
            system=sut,
            name="test",
            parent=twistedPackage,
        )
        twistedAnyTestModule = model.Module(
            system=sut,
            name="other_child",
            parent=twistedTestPackage,
        )

        result = sut.privacyClass(twistedAnyTestModule)

        self.assertIs(result, model.PrivacyClass.HIDDEN)

    def test_privacyClassPublicCode(self):
        """
        Any child of the I{twisted} package has a privacy according to the
        general rules defined in pydoctor.
        """
        sut = TwistedSystem()
        twistedPackage = model.Package(
            system=sut,
            name="twisted",
            parent=None,
        )
        twistedSubProjectPackage = model.Package(
            system=sut,
            name="subproject",
            parent=twistedPackage,
        )
        twistedSubProjectModule = model.Module(
            system=sut,
            name="other_child",
            parent=twistedSubProjectPackage,
        )
        twistedPrivateModule = model.Module(
            system=sut,
            name="_private_child",
            parent=twistedSubProjectPackage,
        )

        result = sut.privacyClass(twistedSubProjectPackage)
        self.assertIs(result, model.PrivacyClass.VISIBLE)

        result = sut.privacyClass(twistedSubProjectModule)
        self.assertIs(result, model.PrivacyClass.VISIBLE)

        result = sut.privacyClass(twistedPrivateModule)
        self.assertIs(result, model.PrivacyClass.PRIVATE)


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
