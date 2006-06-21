
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


# System Imports
from twisted.trial import unittest
from twisted.persisted import sob
from twisted.python import components
import sys, os

try:
    from twisted.web import microdom
    gotMicrodom = True
except ImportError:
    import warnings
    warnings.warn("Not testing xml persistence as twisted.web.microdom "
                  "not available")
    gotMicrodom = False

class Dummy(components.Componentized):
    pass

objects = [
1,
"hello",
(1, "hello"),
[1, "hello"],
{1:"hello"},
]

class FakeModule(object):
    pass

class PersistTestCase(unittest.TestCase):
    def testStyles(self):
        for o in objects:
            p = sob.Persistent(o, '')
            for style in 'xml source pickle'.split():
                if style == 'xml' and not gotMicrodom:
                    continue
                p.setStyle(style)
                p.save(filename='persisttest.'+style)
                o1 = sob.load('persisttest.'+style, style)
                self.failUnlessEqual(o, o1)

    def testStylesBeingSet(self):
        o = Dummy()
        o.foo = 5
        o.setComponent(sob.IPersistable, sob.Persistent(o, 'lala'))
        for style in 'xml source pickle'.split():
            if style == 'xml' and not gotMicrodom:
                continue
            sob.IPersistable(o).setStyle(style)
            sob.IPersistable(o).save(filename='lala.'+style)
            o1 = sob.load('lala.'+style, style)
            self.failUnlessEqual(o.foo, o1.foo)
            self.failUnlessEqual(sob.IPersistable(o1).style, style)


    def testNames(self):
        o = [1,2,3]
        p = sob.Persistent(o, 'object')
        for style in 'xml source pickle'.split():
            if style == 'xml' and not gotMicrodom:
                continue
            p.setStyle(style)
            p.save()
            o1 = sob.load('object.ta'+style[0], style)
            self.failUnlessEqual(o, o1)
            for tag in 'lala lolo'.split():
                p.save(tag)
                o1 = sob.load('object-'+tag+'.ta'+style[0], style)
                self.failUnlessEqual(o, o1)
      
    def testEncryptedStyles(self):
        try:
            import Crypto
        except ImportError:
            raise unittest.SkipTest()
        for o in objects:
            phrase='once I was the king of spain'
            p = sob.Persistent(o, '')
            for style in 'xml source pickle'.split():
                if style == 'xml' and not gotMicrodom:
                    continue
                p.setStyle(style)
                p.save(filename='epersisttest.'+style, passphrase=phrase)
                o1 = sob.load('epersisttest.'+style, style, phrase)
                self.failUnlessEqual(o, o1)

    def testPython(self):
        open("persisttest.python", 'w').write('foo=[1,2,3] ')
        o = sob.loadValueFromFile('persisttest.python', 'foo')
        self.failUnlessEqual(o, [1,2,3])

    def testEncryptedPython(self):
        try:
            import Crypto
        except ImportError:
            raise unittest.SkipTest()
        phrase='once I was the king of spain'
        open("epersisttest.python", 'w').write(
                          sob._encrypt(phrase, 'foo=[1,2,3]'))
        o = sob.loadValueFromFile('epersisttest.python', 'foo', phrase)
        self.failUnlessEqual(o, [1,2,3])

    def testTypeGuesser(self):
        self.assertRaises(KeyError, sob.guessType, "file.blah")
        self.assertEqual('python', sob.guessType("file.py"))
        self.assertEqual('python', sob.guessType("file.tac"))
        self.assertEqual('python', sob.guessType("file.etac"))
        self.assertEqual('pickle', sob.guessType("file.tap"))
        self.assertEqual('pickle', sob.guessType("file.etap"))
        self.assertEqual('source', sob.guessType("file.tas"))
        self.assertEqual('source', sob.guessType("file.etas"))
        if gotMicrodom:
            self.assertEqual('xml', sob.guessType("file.tax"))
            self.assertEqual('xml', sob.guessType("file.etax"))

    def testEverythingEphemeralGetattr(self):
        """
        Verify that _EverythingEphermal.__getattr__ works.
        """
        self.fakeMain.testMainModGetattr = 1

        dirname = self.mktemp()
        os.mkdir(dirname)

        filename = os.path.join(dirname, 'persisttest.ee_getattr')

        f = file(filename, 'w')
        f.write('import __main__\n')
        f.write('if __main__.testMainModGetattr != 1: raise AssertionError\n')
        f.write('app = None\n')
        f.close()

        sob.load(filename, 'source')

    def testEverythingEphemeralSetattr(self):
        """
        Verify that _EverythingEphemeral.__setattr__ won't affect __main__.
        """
        self.fakeMain.testMainModSetattr = 1

        dirname = self.mktemp()
        os.mkdir(dirname)

        filename = os.path.join(dirname, 'persisttest.ee_setattr')
        f = file(filename, 'w')
        f.write('import __main__\n')
        f.write('__main__.testMainModSetattr = 2\n')
        f.write('app = None\n')
        f.close()

        sob.load(filename, 'source')

        self.assertEqual(self.fakeMain.testMainModSetattr, 1)

    def testEverythingEphemeralException(self):
        """
        Test that an exception during load() won't cause _EE to mask __main__
        """
        dirname = self.mktemp()
        os.mkdir(dirname)
        filename = os.path.join(dirname, 'persisttest.ee_exception')

        f = file(filename, 'w')
        f.write('raise ValueError\n')
        f.close()

        self.assertRaises(ValueError, sob.load, filename, 'source')
        self.assertEqual(type(sys.modules['__main__']), FakeModule)

    def setUp(self):
        """
        Replace the __main__ module with a fake one, so that it can be mutated
        in tests
        """
        self.realMain = sys.modules['__main__']
        self.fakeMain = sys.modules['__main__'] = FakeModule()

    def tearDown(self):
        """
        Restore __main__ to its original value
        """
        sys.modules['__main__'] = self.realMain

