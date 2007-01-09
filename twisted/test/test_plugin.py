# Copyright (c) 2005 Divmod, Inc.
# See LICENSE for details.

import sys, errno, os, time

from twisted.trial import unittest
from twisted.python.util import sibpath
from twisted.python.filepath import FilePath

from twisted import plugin, plugins

# Indicates whether or not the unit tests are being run.  This is
# inspected by notestplugin.py
running = False

begintest = '''
from zope.interface import classProvides

from twisted.plugin import ITestPlugin, IPlugin

class FourthTestPlugin:
    classProvides(ITestPlugin,
                  IPlugin)

    def test1():
        pass
    test1 = staticmethod(test1)

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
'''

class PluginTestCase(unittest.TestCase):
    """
    Tests which verify the behavior of the current, active Twisted plugins
    directory.
    """
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

    def _testDetectFilesRemoved(self):
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
                wf.close()

                # Generate a cache with pluginextra in it.
                list(plugin.getPlugins(plugin.ITestPlugin))

            finally:
                self._unimportPythonModule(
                    sys.modules['twisted.plugins.pluginextra'],
                    True)
            plgs = list(plugin.getPlugins(plugin.ITestPlugin))
            self.assertEquals(1, len(plgs))

    def testDetectFilesRemoved(self):
        self._testWithCacheness(self._testDetectFilesRemoved)


    def _testNonExistentPathEntry(self):
        path = self.mktemp()
        self.failIf(os.path.exists(path))
        plugins.__path__.append(path)
        try:
            plgs = list(plugin.getPlugins(plugin.ITestPlugin))
            self.assertEqual(len(plgs), 1)
        finally:
            plugins.__path__.remove(path)


    def test_nonexistentPathEntry(self):
        """
        Test that getCache skips over any entries in a plugin package's
        C{__path__} which do not exist.
        """
        return self._testWithCacheness(self._testNonExistentPathEntry)


    def _testNonDirectoryChildEntry(self):
        path = FilePath(self.mktemp())
        self.failIf(path.exists())
        path.touch()
        child = path.child("test_package").path
        plugins.__path__.append(child)
        try:
            plgs = list(plugin.getPlugins(plugin.ITestPlugin))
            self.assertEqual(len(plgs), 1)
        finally:
            plugins.__path__.remove(child)


    def test_nonDirectoryChildEntry(self):
        """
        Test that getCache skips over any entries in a plugin package's
        C{__path__} which refer to children of paths which are not directories.
        """
        return self._testWithCacheness(self._testNonDirectoryChildEntry)

# This is something like the Twisted plugins file.
pluginInitFile = """
import os, sys
__path__ = [os.path.abspath(os.path.join(x, 'plugindummy', 'plugins')) for x in sys.path]
__all__ = []
"""

systemPluginFile = """
from zope.interface import classProvides
from twisted.plugin import IPlugin, ITestPlugin

class system(object):
    classProvides(IPlugin, ITestPlugin)
"""

devPluginFile = """
from zope.interface import classProvides
from twisted.plugin import IPlugin, ITestPlugin

class system(object):
    classProvides(IPlugin, ITestPlugin)

class dev(object):
    classProvides(IPlugin, ITestPlugin)
"""

appPluginFile = """
from zope.interface import classProvides
from twisted.plugin import IPlugin, ITestPlugin

class app(object):
    classProvides(IPlugin, ITestPlugin)
"""

def _createPluginDummy(entrypath, pluginContent, real=True):
    """
    Create a plugindummy package.
    """
    entrypath.createDirectory()
    pkg = entrypath.child('plugindummy')
    pkg.createDirectory()
    if real:
        pkg.child('__init__.py').setContent('')
    plugs = pkg.child('plugins')
    plugs.createDirectory()
    if real:
        plugs.child('__init__.py').setContent(pluginInitFile)
    if real:
        n = 'plugindummy_builtin.py'
    else:
        n = 'plugindummy_app.py'
    plugs.child(n).setContent(pluginContent)


class DeveloperSetupTests(unittest.TestCase):
    """
    These tests verify things about the plugin system without actually
    interacting with the deployed 'twisted.plugins' package, instead creating a
    temporary package.
    """

    def setUp(self):
        """
        Create a complex environment with multiple entries on sys.path, akin to a
        developer's environment who has a development (trunk) checkout of
        Twisted, a system installed version of Twisted (for their operating
        system's tools) and a project which provides Twisted plugins.
        """
        self.savedPath = sys.path[:]
        self.savedModules = sys.modules.copy()
        self.fakeRoot = FilePath(self.mktemp())
        self.fakeRoot.createDirectory()
        self.systemPath = self.fakeRoot.child('system_path')
        self.devPath = self.fakeRoot.child('development_path')
        self.appPath = self.fakeRoot.child('application_path')
        _createPluginDummy(self.systemPath, systemPluginFile)
        _createPluginDummy(self.devPath, devPluginFile)
        _createPluginDummy(self.appPath, appPluginFile, False)

        # Now we're going to do the system installation.
        sys.path.extend([x.path for x in [self.systemPath,
                                          self.appPath]])
        # Import the module we just added to our path.  (Local scope because
        # this package doesn't exist outside of this test.)
        import plugindummy.plugins
        # Run all the way through the plugins list to cause the
        # L{plugin.getPlugins} generator to write cache files for the system
        # installation.
        list(plugin.getPlugins(plugin.ITestPlugin, plugindummy.plugins))
        self.sysplug = self.systemPath.child('plugindummy').child('plugins')
        self.syscache = self.sysplug.child('dropin.cache')
        # Make sure there's a nice big difference in modification times so that
        # we won't re-build the system cache.
        now = time.time()
        os.utime(self.sysplug.child('plugindummy_builtin.py').path, (now - 5000,)*2)
        os.utime(self.syscache.path, (now - 2000,)*2)
        # For extra realism, let's make sure that the system path is no longer
        # writable.
        os.chmod(self.sysplug.path, 0555)
        os.chmod(self.syscache.path, 0555)
        self.resetEnvironment()
        sys.path.extend([x.path for x in [self.devPath,
                                          self.systemPath,
                                          self.appPath]])


    def resetEnvironment(self):
        """
        Change the Python environment back to what it was before the test was
        started.
        """
        sys.modules.clear()
        sys.modules.update(self.savedModules)
        sys.path[:] = self.savedPath


    def tearDown(self):
        """
        Reset the Python environment to what it was before this test ran, and
        restore permissions on files which were marked read-only so that the
        directory may be cleanly cleaned up.
        """
        self.resetEnvironment()
        # Normally we wouldn't "clean up" the filesystem like this (leaving
        # things for post-test inspection), but if we left the permissions the
        # way they were, we'd be leaving files around that the buildbots
        # couldn't delete, and that would be bad.
        os.chmod(self.sysplug.path, 0777)
        os.chmod(self.syscache.path, 0777)


    def test_newPluginsNotClobbered(self):
        """
        Verify that plugins added in the 'development' path are loadable, even when
        the (now non-importable) system path contains its own idea of the list
        of plugins for a package.
        """
        import plugindummy.plugins

        # Run 3 times: uncached, cached, and then cached again to make sure we
        # didn't overwrite / corrupt the cache on the cached try.
        for x in range(3):
            plugs = list(plugin.getPlugins(
                    plugin.ITestPlugin, plugindummy.plugins))
            self.assertEqual(len(plugs), 3)
            names = [plug.__name__ for plug in plugs]
            self.assertIn('app', names)
            self.assertIn('dev', names)
            self.assertIn('system', names)

