# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python._pydoctor}.
"""
import inspect

from collections import namedtuple

from textwrap import dedent

from twisted.python.compat import _PY3
from twisted.python.reflect import requireModule, namedModule

from twisted.trial.unittest import TestCase, SynchronousTestCase

model = requireModule('pydoctor.model')
pydoctorSkip = None
TwistedSphinxInventory = object
TwistedSystem = object
if model is None:
    pydoctorSkip = 'Pydoctor is not present.'
elif _PY3:
    pydoctorSkip = 'Pydoctor not supported on Python3.'
else:
    # We have a valid pydoctor.
    from twisted.python._pydoctor import TwistedSphinxInventory, TwistedSystem
    from pydoctor import astbuilder


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
            name='twisted',
            docstring='ignored',
            parent=None,
            )
        twistedTestPackage = model.Package(
            system=sut,
            name='test',
            docstring='ignored',
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
            name='twisted',
            docstring='ignored',
            parent=None,
            )
        twistedTestPackage = model.Package(
            system=sut,
            name='test',
            docstring='ignored',
            parent=twistedPackage,
            )
        twistedProtoHelpersModule = model.Module(
            system=sut,
            name='proto_helpers',
            docstring='ignored',
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
            name='twisted',
            docstring='ignored',
            parent=None,
            )
        twistedTestPackage = model.Package(
            system=sut,
            name='test',
            docstring='ignored',
            parent=twistedPackage,
            )
        twistedAnyTestModule = model.Module(
            system=sut,
            name='other_child',
            docstring='ignored',
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
            name='twisted',
            docstring='ignored',
            parent=None,
            )
        twistedSubProjectPackage = model.Package(
            system=sut,
            name='subproject',
            docstring='ignored',
            parent=twistedPackage,
            )
        twistedSubProjectModule = model.Module(
            system=sut,
            name='other_child',
            docstring='ignored',
            parent=twistedSubProjectPackage,
            )
        twistedPrivateModule = model.Module(
            system=sut,
            name='_private_child',
            docstring='ignored',
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
        inventory = TwistedSphinxInventory(
            logger=object(), project_name='Super Duper')

        zopeBaseURL = 'https://zope.tld'
        zopeAPIURL = 'api.html#$'
        inventory._links.update({
            'zope.interface.interfaces.IInterface': (zopeBaseURL, zopeAPIURL),
            'zope.interface.declarations.implementer': (
                zopeBaseURL, zopeAPIURL),
            })

        return inventory


    def test_getLinkExistentInInterSphinx(self):
        """
        Return the full URL based on pre-loaded inter sphinx objects.
        """
        sut = self.getInventoryWithZope()

        result = sut.getLink('zope.interface.interfaces.IInterface')

        self.assertEqual(
            'https://zope.tld/api.html#zope.interface.interfaces.IInterface',
            result)


    def test_getLinkZopeNonExistent(self):
        """
        Any reference to I{zope.interface} which is not in the inter sphinx
        database returns L{None}.
        """
        sut = self.getInventoryWithZope()

        # Interface is at zope.interface.interfaces.IInterface so using the
        # short name will fail to find the url.
        result = sut.getLink('zope.interface.Interface')
        self.assertIsNone(result)
        # Any unknown reference returns None.
        result = sut.getLink('zope.interface.NoSuchReference')
        self.assertIsNone(result)


    def test_getLinkZopeAdapterRegistry(self):
        """
        I{zope.interface.adapter.AdapterRegistry} is a special case for which
        the link the narrative docs is returned as there is no API docs yet.
        """
        sut = self.getInventoryWithZope()

        result = sut.getLink('zope.interface.adapter.AdapterRegistry')

        self.assertEqual('https://zope.tld/adapter.html', result)


    def test_getLinkWin32APIExistingMethod(self):
        """
        Will return a link to the activestate.com python 2.7 API for
        pywin32 methods.
        """
        activeStateURL = (
            'http://docs.activestate.com/activepython/2.7/pywin32/'
            'win32api__FormatMessage_meth.html'
            )
        Response = namedtuple('Animal', 'code')
        response = Response(code=200)
        sut = self.getInventoryWithZope()
        sut._getURLAsHEAD = lambda url: {activeStateURL: response}[url]

        result = sut.getLink('win32api.FormatMessage')

        self.assertEqual(activeStateURL, result)


    def test_getLinkWin32APIUnknown(self):
        """
        Will return L{None} when the auto created link don't exist on the
        activestate.com site.
        """
        activeStateURL = (
            'http://docs.activestate.com/activepython/2.7/pywin32/'
            'win32api__FormatMessage_meth.html'
            )
        Response = namedtuple('Animal', 'code')
        response = Response(code=404)
        sut = self.getInventoryWithZope()
        sut._getURLAsHEAD = lambda url: {activeStateURL: response}[url]

        result = sut.getLink('win32api.FormatMessage')

        self.assertIsNone(result)



def pydoctorModuleFromText(moduleName, text):
    """
    Create a L{pydoctor.model.Module} instance from the given source
    code.

    @param moduleName: The return module's name.
    @type moduleName: L{str}

    @param text: The source code for the module.
    @type text: L{str}

    @return: The parsed module.
    @rtype: L{pydoctor.model.Module}
    """
    system = model.System()
    builder = system.defaultBuilder(system)
    mod = builder.pushModule(moduleName, None)
    builder.popModule()
    ast = astbuilder.parse(dedent(text))
    builder.processModuleAST(ast, mod)
    mod = system.allobjects[moduleName]
    mod.ast = ast
    mod.state = model.PROCESSED
    return mod



class PydoctorModuleFromTextTests(SynchronousTestCase):
    """
    Internal tests for L{pydoctorModuleFromText}.
    """
    skip = pydoctorSkip

    def test_parsesSource(self):
        """
        L{pydoctorModuleFromText} parses source into a
        L{pydoctor.model.Module.}
        """
        source = '''\
        def function():
            """
            This is the docstring.
            """
        '''

        module = pydoctorModuleFromText("<test>", source)

        self.assertEqual(list(module.contents), ["function"])

        function = module.contents["function"]

        self.assertEqual(function.docstring.strip(), "This is the docstring.")



class ActuallyTests(SynchronousTestCase):
    """
    Tests for L{_actually}.
    """
    skip = pydoctorSkip

    def setUp(self):
        self.testModule = namedModule("twisted.python.test._actually_test")


    def test_argumentReturned(self):
        """
        The L{_actually} decorator returns its argument instead of the
        object it decorates.
        """
        self.assertIs(self.testModule.theAlias, self.testModule.theFunction)


    def test_pydoctorUsesDocstring(self):
        """
        Pydoctor creates documentation for the object decorated by
        L{_actually}.
        """
        source = inspect.getsource(self.testModule)
        pydoctorModule = pydoctorModuleFromText(self.testModule.__name__,
                                                source)

        self.assertEqual(
            list(pydoctorModule.contents),
            ["theFunction", "theAlias"]
        )
        self.assertNotEqual(
            pydoctorModule.contents["theAlias"].docstring,
            pydoctorModule.contents["theFunction"].docstring,
        )
