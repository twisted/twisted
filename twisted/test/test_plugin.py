# Copyright (c) 2005 Divmod, Inc.
# See LICENSE for details.

import sys, errno, os, time

from twisted.trial import unittest
from twisted.python.util import sibpath

from twisted import plugin, plugins

# Indicates whether or not the unit tests are being run.  This is
# inspected by notestplugin.py
running = False

begintest = '''
from zope.interface import classProvides
from twisted.python.components import backwardsCompatImplements

from twisted.plugin import ITestPlugin, IPlugin

class FourthTestPlugin:
    classProvides(ITestPlugin,
                  IPlugin)

    def test1():
        pass
    test1 = staticmethod(test1)

backwardsCompatImplements(FourthTestPlugin)
'''

extratest = '''
class FifthTestPlugin:
    """
    More documentation: I hate you.
    """
    classProvides(ITestPlugin,
                  IPlugin)

    def test1():
        pass
    test1 = staticmethod(test1)
backwardsCompatImplements(FifthTestPlugin)
'''

class PluginTestCase(unittest.TestCase):
    def setUp(self):
        global running
        running = True

    def tearDown(self):
        global running
        running = False

    def _unimportPythonModule(self, module, deleteSource=False):
        modulePath = module.__name__.split('.')
        packageName = '.'.join(modulePath[:-1])
        moduleName = modulePath[-1]

        delattr(sys.modules[packageName], moduleName)
        del sys.modules[module.__name__]
        for ext in ['c', 'o'] + (deleteSource and [''] or []):
            try:
                os.remove(module.__file__ + ext)
            except OSError, ose:
                if ose.errno != errno.ENOENT:
                    raise

    def _clearCache(self):
        try:
            os.remove(sibpath(plugins.__file__, 'dropin.cache'))
        except OSError, ose:
            if ose.errno in (errno.EACCES, errno.ENOENT):
                print 'Testing in deployed mode.'
            else:
                raise

    def _testWithCacheness(self, meth):
        meth()
        meth()
        self._clearCache()
        meth()
        meth()

    def _testCache(self):
        cache = plugin.getCache(plugins)

        dropin = cache['testplugin']
        self.assertEquals(dropin.moduleName, 'twisted.plugins.testplugin')
        self.assertNotEquals(dropin.description.find("I'm a test drop-in."), -1)

        # Note, not the preferred way to get a plugin by its interface.
        p1 = [p for p in dropin.plugins if plugin.ITestPlugin in p.provided][0]
        self.assertIdentical(p1.dropin, dropin)
        self.assertEquals(p1.name, "TestPlugin")
        self.assertEquals(
            p1.description.strip(),
            "A plugin used solely for testing purposes.")
        self.assertEquals(p1.provided, [plugin.ITestPlugin, plugin.IPlugin])
        realPlugin = p1.load()
        self.assertIdentical(realPlugin,
                             sys.modules['twisted.plugins.testplugin'].TestPlugin)

        import twisted.plugins.testplugin as tp
        self.assertIdentical(realPlugin, tp.TestPlugin)

    def testCache(self):
        self._testWithCacheness(self._testCache)

    def _testPlugins(self):
        plugins = list(plugin.getPlugins(plugin.ITestPlugin2))

        self.assertEquals(len(plugins), 2)

        names = ['AnotherTestPlugin', 'ThirdTestPlugin']
        for p in plugins:
            names.remove(p.__name__)
            p.test()

    def testPlugins(self):
        self._testWithCacheness(self._testPlugins)

    def _testDetectNewFiles(self):
        writeFileName = sibpath(plugins.__file__, 'pluginextra.py')
        try:
            wf = file(writeFileName, 'w')
        except IOError, ioe:
            if ioe.errno == errno.EACCES:
                raise unittest.SkipTest(
                    "No permission to add things to twisted.plugins")
            else:
                raise
        else:
            try:
                wf.write(begintest)
                wf.flush()

                self.failIfIn('twisted.plugins.pluginextra', sys.modules)
                self.failIf(hasattr(sys.modules['twisted.plugins'], 'pluginextra'),
                            "plugins package still has pluginextra module")

                plgs = list(plugin.getPlugins(plugin.ITestPlugin))

                self.assertEquals(
                    len(plgs), 2,
                    "Unexpected plugins found: %r" % (
                        [p.__name__ for p in plgs]))

                names = ['TestPlugin', 'FourthTestPlugin']
                for p in plgs:
                    names.remove(p.__name__)
                    p.test1()
            finally:
                wf.close()
                self._unimportPythonModule(
                    sys.modules['twisted.plugins.pluginextra'],
                    True)

    def testDetectNewFiles(self):
        self._testWithCacheness(self._testDetectNewFiles)

    def _testDetectFilesChanged(self):
        writeFileName = sibpath(plugins.__file__, 'pluginextra.py')
        try:
            writeFile = file(writeFileName, 'w')
        except IOError, ioe:
            if ioe.errno == errno.EACCES:
                raise unittest.SkipTest(
                    "No permission to add things to twisted.plugins")
            else:
                raise
        try:
            writeFile.write(begintest)
            writeFile.flush()
            plgs = list(plugin.getPlugins(plugin.ITestPlugin))
            # Sanity check
            self.assertEquals(
                len(plgs), 2,
                "Unexpected plugins found: %r" % (
                    [p.__name__ for p in plgs]))

            writeFile.write(extratest)
            writeFile.flush()

            # Fake out Python.
            self._unimportPythonModule(sys.modules['twisted.plugins.pluginextra'])

            # Make sure additions are noticed
            plgs = list(plugin.getPlugins(plugin.ITestPlugin))

            self.assertEquals(len(plgs), 3, "Unexpected plugins found: %r" % (
                    [p.__name__ for p in plgs]))

            names = ['TestPlugin', 'FourthTestPlugin', 'FifthTestPlugin']
            for p in plgs:
                names.remove(p.__name__)
                p.test1()
        finally:
            writeFile.close()
            self._unimportPythonModule(
                sys.modules['twisted.plugins.pluginextra'],
                True)

    def testDetectFilesChanged(self):
        self._testWithCacheness(self._testDetectFilesChanged)
