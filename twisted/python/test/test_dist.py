# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for parts of our release automation system.
"""


import os

from distutils.core import Distribution

from twisted.trial.unittest import TestCase

from twisted.python import dist
from twisted.python.dist import (get_setup_args, ConditionalExtension,
                                 install_data_twisted, build_scripts_twisted,
                                 getDataFiles)
from twisted.python.filepath import FilePath


class SetupTest(TestCase):
    """
    Tests for L{get_setup_args}.
    """
    def test_conditionalExtensions(self):
        """
        Passing C{conditionalExtensions} as a list of L{ConditionalExtension}
        objects to get_setup_args inserts a custom build_ext into the result
        which knows how to check whether they should be.
        """
        good_ext = ConditionalExtension("whatever", ["whatever.c"],
                                        condition=lambda b: True)
        bad_ext = ConditionalExtension("whatever", ["whatever.c"],
                                        condition=lambda b: False)
        args = get_setup_args(conditionalExtensions=[good_ext, bad_ext])
        # ext_modules should be set even though it's not used.  See comment
        # in get_setup_args
        self.assertEquals(args["ext_modules"], [good_ext, bad_ext])
        cmdclass = args["cmdclass"]
        build_ext = cmdclass["build_ext"]
        builder = build_ext(Distribution())
        builder.prepare_extensions()
        self.assertEquals(builder.extensions, [good_ext])


    def test_win32Definition(self):
        """
        When building on Windows NT, the WIN32 macro will be defined as 1.
        """
        ext = ConditionalExtension("whatever", ["whatever.c"],
                                   define_macros=[("whatever", 2)])
        args = get_setup_args(conditionalExtensions=[ext])
        builder = args["cmdclass"]["build_ext"](Distribution())
        self.patch(os, "name", "nt")
        builder.prepare_extensions()
        self.assertEquals(ext.define_macros, [("whatever", 2), ("WIN32", 1)])


    def test_defaultCmdClasses(self):
        """
        get_setup_args supplies default values for the cmdclass keyword.
        """
        args = get_setup_args()
        self.assertIn('cmdclass', args)
        cmdclass = args['cmdclass']
        self.assertIn('install_data', cmdclass)
        self.assertEquals(cmdclass['install_data'], install_data_twisted)
        self.assertIn('build_scripts', cmdclass)
        self.assertEquals(cmdclass['build_scripts'], build_scripts_twisted)


    def test_settingCmdClasses(self):
        """
        get_setup_args allows new cmdclasses to be added.
        """
        args = get_setup_args(cmdclass={'foo': 'bar'})
        self.assertEquals(args['cmdclass']['foo'], 'bar')


    def test_overridingCmdClasses(self):
        """
        get_setup_args allows choosing which defaults to override.
        """
        args = get_setup_args(cmdclass={'install_data': 'baz'})

        # Overridden cmdclass should be overridden
        self.assertEquals(args['cmdclass']['install_data'], 'baz')

        # Non-overridden cmdclasses should still be set to defaults.
        self.assertEquals(args['cmdclass']['build_scripts'],
                          build_scripts_twisted)



class GetVersionTest(TestCase):
    """
    Tests for L{dist.getVersion}.
    """

    def setUp(self):
        self.dirname = self.mktemp()
        os.mkdir(self.dirname)

    def test_getVersionCore(self):
        """
        Test that getting the version of core reads from the
        [base]/_version.py file.
        """
        f = open(os.path.join(self.dirname, "_version.py"), "w")
        f.write("""
from twisted.python import versions
version = versions.Version("twisted", 0, 1, 2)
""")
        f.close()
        self.assertEquals(dist.getVersion("core", base=self.dirname), "0.1.2")

    def test_getVersionOther(self):
        """
        Test that getting the version of a non-core project reads from
        the [base]/[projname]/_version.py file.
        """
        os.mkdir(os.path.join(self.dirname, "blat"))
        f = open(os.path.join(self.dirname, "blat", "_version.py"), "w")
        f.write("""
from twisted.python import versions
version = versions.Version("twisted.blat", 9, 8, 10)
""")
        f.close()
        self.assertEquals(dist.getVersion("blat", base=self.dirname), "9.8.10")


class GetScriptsTest(TestCase):

    def test_scriptsInSVN(self):
        """
        getScripts should return the scripts associated with a project
        in the context of Twisted SVN.
        """
        basedir = self.mktemp()
        os.mkdir(basedir)
        os.mkdir(os.path.join(basedir, 'bin'))
        os.mkdir(os.path.join(basedir, 'bin', 'proj'))
        f = open(os.path.join(basedir, 'bin', 'proj', 'exy'), 'w')
        f.write('yay')
        f.close()
        scripts = dist.getScripts('proj', basedir=basedir)
        self.assertEquals(len(scripts), 1)
        self.assertEquals(os.path.basename(scripts[0]), 'exy')


    def test_scriptsInRelease(self):
        """
        getScripts should return the scripts associated with a project
        in the context of a released subproject tarball.
        """
        basedir = self.mktemp()
        os.mkdir(basedir)
        os.mkdir(os.path.join(basedir, 'bin'))
        f = open(os.path.join(basedir, 'bin', 'exy'), 'w')
        f.write('yay')
        f.close()
        scripts = dist.getScripts('proj', basedir=basedir)
        self.assertEquals(len(scripts), 1)
        self.assertEquals(os.path.basename(scripts[0]), 'exy')


    def test_noScriptsInSVN(self):
        """
        When calling getScripts for a project which doesn't actually
        have any scripts, in the context of an SVN checkout, an
        empty list should be returned.
        """
        basedir = self.mktemp()
        os.mkdir(basedir)
        os.mkdir(os.path.join(basedir, 'bin'))
        os.mkdir(os.path.join(basedir, 'bin', 'otherproj'))
        scripts = dist.getScripts('noscripts', basedir=basedir)
        self.assertEquals(scripts, [])


    def test_getScriptsTopLevel(self):
        """
        Passing the empty string to getScripts returns scripts that are (only)
        in the top level bin directory.
        """
        basedir = FilePath(self.mktemp())
        basedir.createDirectory()
        bindir = basedir.child("bin")
        bindir.createDirectory()
        included = bindir.child("included")
        included.setContent("yay included")
        subdir = bindir.child("subdir")
        subdir.createDirectory()
        subdir.child("not-included").setContent("not included")

        scripts = dist.getScripts("", basedir=basedir.path)
        self.assertEquals(scripts, [included.path])


    def test_noScriptsInSubproject(self):
        """
        When calling getScripts for a project which doesn't actually
        have any scripts in the context of that project's individual
        project structure, an empty list should be returned.
        """
        basedir = self.mktemp()
        os.mkdir(basedir)
        scripts = dist.getScripts('noscripts', basedir=basedir)
        self.assertEquals(scripts, [])



class GetDataFilesTests(TestCase):
    """
    Tests for L{getDataFiles}.
    """

    def _makeBaseDir(self):
        """
        Make a directory for getDataFiles to search.
        """
        rawBaseDir = os.path.join(".", self.mktemp())
        baseDir = FilePath(rawBaseDir)
        baseDir.makedirs()

        return rawBaseDir, baseDir


    def test_basicOperation(self):
        """
        L{getDataFiles} finds a single data file in a given directory.
        """
        # The directory where we'll put our data file.
        rawBaseDir, baseDir = self._makeBaseDir()

        # A data file to be found.
        baseDir.child("foo.txt").touch()

        results = getDataFiles(baseDir.path)
        self.assertEquals(
            results,
            [(rawBaseDir, [os.path.join(rawBaseDir, "foo.txt")])])


    def test_directoryRecursion(self):
        """
        L{getDataFiles} searches for data files inside subdirectories.
        """
        rawBaseDir, baseDir = self._makeBaseDir()

        subDir = baseDir.child("foo")
        subDir.makedirs()

        subDir.child("bar.txt").touch()

        subSubDir = subDir.child("baz")
        subSubDir.makedirs()

        subSubDir.child("qux.txt").touch()

        results = getDataFiles(baseDir.path)
        self.assertEquals(
            results,
            [(os.path.join(rawBaseDir, "foo"),
              [os.path.join(rawBaseDir, "foo", "bar.txt")]),
             (os.path.join(rawBaseDir, "foo", "baz"),
              [os.path.join(rawBaseDir, "foo", "baz", "qux.txt")])])


    def test_ignoreVCSMetadata(self):
        """
        L{getDataFiles} ignores Subversion metadata files.
        """
        rawBaseDir, baseDir = self._makeBaseDir()

        # Top-level directory contains a VCS dir, containing ignorable data.
        vcsDir = baseDir.child(".svn")
        vcsDir.makedirs()
        vcsDir.child("data.txt").touch()

        # Subdirectory contains a valid data file.
        subDir = baseDir.child("foo")
        subDir.makedirs()
        subDir.child("bar.txt").touch()

        # Subdirectory contains another VCS dir, with more ignorable data.
        subVcsDir = subDir.child("_darcs")
        subVcsDir.makedirs()
        subVcsDir.child("data.txt").touch()

        # Subdirectory contains an ignorable VCS file.
        subDir.child(".cvsignore").touch()

        results = getDataFiles(baseDir.path)
        self.assertEquals(
            results,
            [(os.path.join(rawBaseDir, "foo"),
              [os.path.join(rawBaseDir, "foo", "bar.txt")])])


    def test_ignoreArbitrarySubdirectories(self):
        """
        L{getDataFiles} ignores any filenames it's asked to ignore.
        """
        rawBaseDir, baseDir = self._makeBaseDir()

        subDir = baseDir.child("foo")
        subDir.makedirs()

        # Make an ordinary subdirectory with some data files.
        subDir.child("bar.txt").touch()
        subDir.child("ignorable").touch() # not a dir, won't be ignored

        # Make a subdirectory with an ignorable name, and some data files.
        ignorableSubDir = baseDir.child("ignorable")
        ignorableSubDir.makedirs()
        ignorableSubDir.child("bar.txt").touch()

        results = getDataFiles(baseDir.path, ignore=["ignorable"])
        self.assertEquals(
            results,
            [(os.path.join(rawBaseDir, "foo"),
              [os.path.join(rawBaseDir, "foo", "bar.txt"),
               os.path.join(rawBaseDir, "foo", "ignorable")])])


    def test_ignoreNonDataFiles(self):
        """
        L{getDataFiles} ignores Python code, backup files and bytecode.
        """
        rawBaseDir, baseDir = self._makeBaseDir()

        # All these are not data files, and should be ignored.
        baseDir.child("module.py").touch()
        baseDir.child("module.pyc").touch()
        baseDir.child("module.pyo").touch()

        subDir = baseDir.child("foo")
        subDir.makedirs()

        subDir.child("bar.txt").touch()

        # An editor-made backup of bar.txt should be ignored.
        subDir.child("bar.txt~").touch()

        results = getDataFiles(baseDir.path)
        self.assertEquals(
            results,
            [(os.path.join(rawBaseDir, "foo"),
              [os.path.join(rawBaseDir, "foo", "bar.txt")])])


    def test_pathsRelativeToParent(self):
        """
        L{getDataFiles} returns paths relative to the parent parameter.
        """
        rawBaseDir, baseDir = self._makeBaseDir()

        # munge rawBaseDir in a way that we can recognise later.
        mungedBaseDir = os.path.join(rawBaseDir, "foo/../")

        subDir = baseDir.child("foo")
        subDir.makedirs()

        subDir.child("bar.txt").touch()

        results = getDataFiles(subDir.path, parent=mungedBaseDir)
        self.assertEquals(
            results,
            [(os.path.join(mungedBaseDir, "foo"),
              [os.path.join(mungedBaseDir, "foo", "bar.txt")])])
