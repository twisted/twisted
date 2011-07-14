
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Test cases for explorer
"""

from twisted.trial import unittest

from twisted.manhole import explorer

import types

"""
# Tests:

 Get an ObjectLink.  Browse ObjectLink.identifier.  Is it the same?

 Watch Object.  Make sure an ObjectLink is received when:
   Call a method.
   Set an attribute.

 Have an Object with a setattr class.  Watch it.
   Do both the navite setattr and the watcher get called?

 Sequences with circular references.  Does it blow up?
"""

class SomeDohickey:
    def __init__(self, *a):
        self.__dict__['args'] = a

    def bip(self):
        return self.args


class TestBrowser(unittest.TestCase):
    def setUp(self):
        self.pool = explorer.explorerPool
        self.pool.clear()
        self.testThing = ["How many stairs must a man climb down?",
                          SomeDohickey(42)]

    def test_chain(self):
        "Following a chain of Explorers."
        xplorer = self.pool.getExplorer(self.testThing, 'testThing')
        self.assertEqual(xplorer.id, id(self.testThing))
        self.assertEqual(xplorer.identifier, 'testThing')

        dxplorer = xplorer.get_elements()[1]
        self.assertEqual(dxplorer.id, id(self.testThing[1]))

class Watcher:
    zero = 0
    def __init__(self):
        self.links = []

    def receiveBrowserObject(self, olink):
        self.links.append(olink)

    def setZero(self):
        self.zero = len(self.links)

    def len(self):
        return len(self.links) - self.zero


class SetattrDohickey:
    def __setattr__(self, k, v):
        v = list(str(v))
        v.reverse()
        self.__dict__[k] = ''.join(v)

class MiddleMan(SomeDohickey, SetattrDohickey):
    pass

# class TestWatch(unittest.TestCase):
class FIXME_Watch:
    def setUp(self):
        self.globalNS = globals().copy()
        self.localNS = {}
        self.browser = explorer.ObjectBrowser(self.globalNS, self.localNS)
        self.watcher = Watcher()

    def test_setAttrPlain(self):
        "Triggering a watcher response by setting an attribute."

        testThing = SomeDohickey('pencil')
        self.browser.watchObject(testThing, 'testThing',
                                 self.watcher.receiveBrowserObject)
        self.watcher.setZero()

        testThing.someAttr = 'someValue'

        self.assertEqual(testThing.someAttr, 'someValue')
        self.failUnless(self.watcher.len())
        olink = self.watcher.links[-1]
        self.assertEqual(olink.id, id(testThing))

    def test_setAttrChain(self):
        "Setting an attribute on a watched object that has __setattr__"
        testThing = MiddleMan('pencil')

        self.browser.watchObject(testThing, 'testThing',
                                 self.watcher.receiveBrowserObject)
        self.watcher.setZero()

        testThing.someAttr = 'ZORT'

        self.assertEqual(testThing.someAttr, 'TROZ')
        self.failUnless(self.watcher.len())
        olink = self.watcher.links[-1]
        self.assertEqual(olink.id, id(testThing))


    def test_method(self):
        "Triggering a watcher response by invoking a method."

        for testThing in (SomeDohickey('pencil'), MiddleMan('pencil')):
            self.browser.watchObject(testThing, 'testThing',
                                     self.watcher.receiveBrowserObject)
            self.watcher.setZero()

            rval = testThing.bip()
            self.assertEqual(rval, ('pencil',))

            self.failUnless(self.watcher.len())
            olink = self.watcher.links[-1]
            self.assertEqual(olink.id, id(testThing))


def function_noArgs():
    "A function which accepts no arguments at all."
    return

def function_simple(a, b, c):
    "A function which accepts several arguments."
    return a, b, c

def function_variable(*a, **kw):
    "A function which accepts a variable number of args and keywords."
    return a, kw

def function_crazy((alpha, beta), c, d=range(4), **kw):
    "A function with a mad crazy signature."
    return alpha, beta, c, d, kw

class TestBrowseFunction(unittest.TestCase):

    def setUp(self):
        self.pool = explorer.explorerPool
        self.pool.clear()

    def test_sanity(self):
        """Basic checks for browse_function.

        Was the proper type returned?  Does it have the right name and ID?
        """
        for f_name in ('function_noArgs', 'function_simple',
                       'function_variable', 'function_crazy'):
            f = eval(f_name)

            xplorer = self.pool.getExplorer(f, f_name)

            self.assertEqual(xplorer.id, id(f))

            self.failUnless(isinstance(xplorer, explorer.ExplorerFunction))

            self.assertEqual(xplorer.name, f_name)

    def test_signature_noArgs(self):
        """Testing zero-argument function signature.
        """

        xplorer = self.pool.getExplorer(function_noArgs, 'function_noArgs')

        self.assertEqual(len(xplorer.signature), 0)

    def test_signature_simple(self):
        """Testing simple function signature.
        """

        xplorer = self.pool.getExplorer(function_simple, 'function_simple')

        expected_signature = ('a','b','c')

        self.assertEqual(xplorer.signature.name, expected_signature)

    def test_signature_variable(self):
        """Testing variable-argument function signature.
        """

        xplorer = self.pool.getExplorer(function_variable,
                                        'function_variable')

        expected_names = ('a','kw')
        signature = xplorer.signature

        self.assertEqual(signature.name, expected_names)
        self.failUnless(signature.is_varlist(0))
        self.failUnless(signature.is_keyword(1))

    def test_signature_crazy(self):
        """Testing function with crazy signature.
        """
        xplorer = self.pool.getExplorer(function_crazy, 'function_crazy')

        signature = xplorer.signature

        expected_signature = [{'name': 'c'},
                              {'name': 'd',
                               'default': range(4)},
                              {'name': 'kw',
                               'keywords': 1}]

        # The name of the first argument seems to be indecipherable,
        # but make sure it has one (and no default).
        self.failUnless(signature.get_name(0))
        self.failUnless(not signature.get_default(0)[0])

        self.assertEqual(signature.get_name(1), 'c')

        # Get a list of values from a list of ExplorerImmutables.
        arg_2_default = map(lambda l: l.value,
                            signature.get_default(2)[1].get_elements())

        self.assertEqual(signature.get_name(2), 'd')
        self.assertEqual(arg_2_default, range(4))

        self.assertEqual(signature.get_name(3), 'kw')
        self.failUnless(signature.is_keyword(3))

if __name__ == '__main__':
    unittest.main()
