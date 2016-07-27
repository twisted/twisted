# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.release} and L{twisted.python._release}.

All of these tests are skipped on platforms other than Linux, as the release is
only ever performed on Linux.
"""

from __future__ import print_function

import glob
import operator
import os
import sys
import textwrap
import tempfile
import shutil

from datetime import date
from io import BytesIO as StringIO

from twisted.trial.unittest import TestCase

from twisted.python.compat import execfile
from twisted.python.procutils import which
from twisted.python import release
from twisted.python.filepath import FilePath
from twisted.python.versions import Version

from subprocess import CalledProcessError

from twisted.python._release import (
    _changeVersionInFile, getNextVersion, findTwistedProjects, replaceInFile,
    replaceProjectVersion, Project, generateVersionFileData,
    changeAllProjectVersions, VERSION_OFFSET, filePathDelta,
    APIBuilder, BuildAPIDocsScript, CheckTopfileScript,
    runCommand, NotWorkingDirectory,
    ChangeVersionsScript, NewsBuilder, SphinxBuilder,
    GitCommand, getRepositoryCommand, IVCSCommand)

if os.name != 'posix':
    skip = "Release toolchain only supported on POSIX."
else:
    skip = None

testingSphinxConf = "master_doc = 'index'\n"

try:
    import pydoctor.driver
    # it might not be installed, or it might use syntax not available in
    # this version of Python.
except (ImportError, SyntaxError):
    pydoctorSkip = "Pydoctor is not present."
else:
    if getattr(pydoctor, "version_info", (0,)) < (0, 1):
        pydoctorSkip = "Pydoctor is too old."
    else:
        pydoctorSkip = skip


if not skip and which("sphinx-build"):
    sphinxSkip = None
else:
    sphinxSkip = "Sphinx not available."


if not skip and which("git"):
    gitVersion = runCommand(["git", "--version"]).split(" ")[2].split(".")

    # We want git 2.0 or above.
    if int(gitVersion[0]) >= 2:
        gitSkip = skip
    else:
        gitSkip = "old git is present"
else:
    gitSkip = "git is not present."



class ExternalTempdirTestCase(TestCase):
    """
    A test case which has mkdir make directories outside of the usual spot, so
    that Git commands don't interfere with the Twisted checkout.
    """
    def mktemp(self):
        """
        Make our own directory.
        """
        newDir = tempfile.mkdtemp(dir="/tmp/")
        self.addCleanup(shutil.rmtree, newDir)
        return newDir



def _gitConfig(path):
    """
    Set some config in the repo that Git requires to make commits. This isn't
    needed in real usage, just for tests.

    @param path: The path to the Git repository.
    @type path: L{FilePath}
    """
    runCommand(["git", "config",
                "--file", path.child(".git").child("config").path,
                "user.name", '"someone"'])
    runCommand(["git", "config",
                "--file", path.child(".git").child("config").path,
                "user.email", '"someone@someplace.com"'])



def _gitInit(path):
    """
    Run a git init, and set some config that git requires. This isn't needed in
    real usage.

    @param path: The path to where the Git repo will be created.
    @type path: L{FilePath}
    """
    runCommand(["git", "init", path.path])
    _gitConfig(path)



def genVersion(*args, **kwargs):
    """
    A convenience for generating _version.py data.

    @param args: Arguments to pass to L{Version}.
    @param kwargs: Keyword arguments to pass to L{Version}.
    """
    return generateVersionFileData(Version(*args, **kwargs))



class StructureAssertingMixin(object):
    """
    A mixin for L{TestCase} subclasses which provides some methods for
    asserting the structure and contents of directories and files on the
    filesystem.
    """
    def createStructure(self, root, dirDict):
        """
        Create a set of directories and files given a dict defining their
        structure.

        @param root: The directory in which to create the structure.  It must
            already exist.
        @type root: L{FilePath}

        @param dirDict: The dict defining the structure. Keys should be strings
            naming files, values should be strings describing file contents OR
            dicts describing subdirectories.  All files are written in binary
            mode.  Any string values are assumed to describe text files and
            will have their newlines replaced with the platform-native newline
            convention.  For example::

                {"foofile": "foocontents",
                 "bardir": {"barfile": "bar\ncontents"}}
        @type dirDict: C{dict}
        """
        for x in dirDict:
            child = root.child(x)
            if isinstance(dirDict[x], dict):
                child.createDirectory()
                self.createStructure(child, dirDict[x])
            else:
                child.setContent(dirDict[x].replace('\n', os.linesep))

    def assertStructure(self, root, dirDict):
        """
        Assert that a directory is equivalent to one described by a dict.

        @param root: The filesystem directory to compare.
        @type root: L{FilePath}
        @param dirDict: The dict that should describe the contents of the
            directory. It should be the same structure as the C{dirDict}
            parameter to L{createStructure}.
        @type dirDict: C{dict}
        """
        children = [each.basename() for each in root.children()]
        for pathSegment, expectation in dirDict.items():
            child = root.child(pathSegment)
            if callable(expectation):
                self.assertTrue(expectation(child))
            elif isinstance(expectation, dict):
                self.assertTrue(child.isdir(), "%s is not a dir!"
                                % (child.path,))
                self.assertStructure(child, expectation)
            else:
                actual = child.getContent().replace(os.linesep, '\n')
                self.assertEqual(actual, expectation)
            children.remove(pathSegment)
        if children:
            self.fail("There were extra children in %s: %s"
                      % (root.path, children))



class ChangeVersionTests(ExternalTempdirTestCase, StructureAssertingMixin):
    """
    Twisted has the ability to change versions.
    """

    def makeFile(self, relativePath, content):
        """
        Create a file with the given content relative to a temporary directory.

        @param relativePath: The basename of the file to create.
        @param content: The content that the file will have.
        @return: The filename.
        """
        baseDirectory = FilePath(self.mktemp())
        directory, filename = os.path.split(relativePath)
        directory = baseDirectory.preauthChild(directory)
        file = directory.child(filename)
        directory.child(filename).setContent(content)
        return file


    def test_getNextVersion(self):
        """
        When calculating the next version to release when a release is
        happening in the same year as the last release, the minor version
        number is incremented.
        """
        now = date.today()
        major = now.year - VERSION_OFFSET
        version = Version("twisted", major, 9, 0)
        self.assertEqual(
            getNextVersion(version, prerelease=False, patch=False, today=now),
            Version("twisted", major, 10, 0))


    def test_getNextVersionAfterYearChange(self):
        """
        When calculating the next version to release when a release is
        happening in a later year, the minor version number is reset to 0.
        """
        now = date.today()
        major = now.year - VERSION_OFFSET
        version = Version("twisted", major - 1, 9, 0)
        self.assertEqual(
            getNextVersion(version, prerelease=False, patch=False, today=now),
            Version("twisted", major, 0, 0))


    def test_getNextVersionPreRelease(self):
        """
        L{getNextVersion} updates the major to the current year, and resets the
        minor when creating a pre-release.
        """
        now = date.today()
        major = now.year - VERSION_OFFSET
        version = Version("twisted", 3, 9, 0)
        self.assertEqual(
            getNextVersion(version, prerelease=True, patch=False, today=now),
            Version("twisted", major, 0, 0, 1))


    def test_getNextVersionFinalRelease(self):
        """
        L{getNextVersion} resets the pre-release count when making a final
        release after a pre-release.
        """
        now = date.today()
        version = Version("twisted", 3, 9, 0, 1)
        self.assertEqual(
            getNextVersion(version, prerelease=False, patch=False, today=now),
            Version("twisted", 3, 9, 0))


    def test_getNextVersionNextPreRelease(self):
        """
        L{getNextVersion} just increments the pre-release number when operating
        on a pre-release.
        """
        now = date.today()
        version = Version("twisted", 3, 9, 1, 1)
        self.assertEqual(
            getNextVersion(version, prerelease=True, patch=False, today=now),
            Version("twisted", 3, 9, 1, 2))


    def test_getNextVersionPatchRelease(self):
        """
        L{getNextVersion} sets the micro number when creating a patch release.
        """
        now = date.today()
        version = Version("twisted", 3, 9, 0)
        self.assertEqual(
            getNextVersion(version, prerelease=False, patch=True, today=now),
            Version("twisted", 3, 9, 1))


    def test_getNextVersionNextPatchRelease(self):
        """
        L{getNextVersion} just increments the micro number when creating a
        patch release.
        """
        now = date.today()
        version = Version("twisted", 3, 9, 1)
        self.assertEqual(
            getNextVersion(version, prerelease=False, patch=True, today=now),
            Version("twisted", 3, 9, 2))


    def test_getNextVersionNextPatchPreRelease(self):
        """
        L{getNextVersion} updates both the micro version and the pre-release
        count when making a patch pre-release.
        """
        now = date.today()
        version = Version("twisted", 3, 9, 1)
        self.assertEqual(
            getNextVersion(version, prerelease=True, patch=True, today=now),
            Version("twisted", 3, 9, 2, 1))


    def test_changeVersionInFile(self):
        """
        _changeVersionInFile replaces the old version information in a file
        with the given new version information.
        """
        # The version numbers are arbitrary, the name is only kind of
        # arbitrary.
        packageName = 'foo'
        oldVersion = Version(packageName, 2, 5, 0)
        file = self.makeFile('README',
                             "Hello and welcome to %s." % oldVersion.base())

        newVersion = Version(packageName, 7, 6, 0)
        _changeVersionInFile(oldVersion, newVersion, file.path)

        self.assertEqual(file.getContent(),
                         "Hello and welcome to %s." % newVersion.base())


    def test_changeAllProjectVersions(self):
        """
        L{changeAllProjectVersions} changes the version numbers in the
        _version.py
        and README file.
        """
        root = FilePath(self.mktemp())
        structure = {
            "README.rst": "Hi this is 1.0.0.",
            "twisted": {
                "topfiles": {
                    "README": "Hi this is 1.0.0"},
                "_version.py": genVersion("twisted", 1, 0, 0)
                }
            }
        self.createStructure(root, structure)
        releaseDate = date(2010, 1, 1)
        changeAllProjectVersions(root, False, False, releaseDate)
        outStructure = {
            "README.rst": "Hi this is 10.0.0.",
            "twisted": {
                "topfiles": {
                    "README": "Hi this is 10.0.0"},
                "_version.py": genVersion("twisted", 10, 0, 0),
            }}
        self.assertStructure(root, outStructure)


    def test_changeAllProjectVersionsPreRelease(self):
        """
        L{changeAllProjectVersions} changes all version numbers in _version.py
        and README files for all projects as well as in the top-level
        README file. If the old version was a pre-release, it will change the
        version in NEWS files as well.
        """
        root = FilePath(self.mktemp())

        coreNews = ("Twisted Core 1.0.0pre1 (2009-12-25)\n"
                    "===============================\n"
                    "\n")
        webNews = ("Twisted Web 1.0.0pre1 (2009-12-25)\n"
                   "==================================\n"
                   "\n")
        structure = {
            "README.rst": "Hi this is 1.0.0pre1.",
            "NEWS": coreNews + webNews,
            "twisted": {
                "topfiles": {
                    "README": "Hi this is 1.0.0pre1",
                    "NEWS": coreNews},
                "_version.py": genVersion("twisted", 1, 0, 0, 1),
                "web": {
                    "topfiles": {
                        "README": "Hi this is 1.0.0pre1",
                        "NEWS": webNews}
                }}}
        self.createStructure(root, structure)
        releaseDate = date(2010, 1, 1)
        changeAllProjectVersions(root, False, False, releaseDate)
        coreNews = ("Twisted Core 1.0.0 (2010-01-01)\n"
                    "===============================\n"
                    "\n")
        webNews = ("Twisted Web 1.0.0 (2010-01-01)\n"
                   "==============================\n"
                   "\n")
        outStructure = {
            "README.rst": "Hi this is 1.0.0.",
            "NEWS": coreNews + webNews,
            "twisted": {
                "topfiles": {
                    "README": "Hi this is 1.0.0",
                    "NEWS": coreNews},
                "_version.py": genVersion("twisted", 1, 0, 0),
                "web": {
                    "topfiles": {
                        "README": "Hi this is 1.0.0",
                        "NEWS": webNews}
                }}}
        self.assertStructure(root, outStructure)



class ProjectTests(ExternalTempdirTestCase):
    """
    There is a first-class representation of a project.
    """

    def assertProjectsEqual(self, observedProjects, expectedProjects):
        """
        Assert that two lists of L{Project}s are equal.
        """
        self.assertEqual(len(observedProjects), len(expectedProjects))
        observedProjects = sorted(observedProjects,
                                  key=operator.attrgetter('directory'))
        expectedProjects = sorted(expectedProjects,
                                  key=operator.attrgetter('directory'))
        for observed, expected in zip(observedProjects, expectedProjects):
            self.assertEqual(observed.directory, expected.directory)


    def makeProject(self, version, baseDirectory=None):
        """
        Make a Twisted-style project in the given base directory.

        @param baseDirectory: The directory to create files in
            (as a L{FilePath).
        @param version: The version information for the project.
        @return: L{Project} pointing to the created project.
        """
        if baseDirectory is None:
            baseDirectory = FilePath(self.mktemp())
        segments = version.package.split('.')
        directory = baseDirectory
        for segment in segments:
            directory = directory.child(segment)
            if not directory.exists():
                directory.createDirectory()
            directory.child('__init__.py').setContent('')
        directory.child('topfiles').createDirectory()
        directory.child('topfiles').child('README').setContent(version.base())
        replaceProjectVersion(
            directory.child('_version.py').path, version)
        return Project(directory)


    def makeProjects(self, *versions):
        """
        Create a series of projects underneath a temporary base directory.

        @return: A L{FilePath} for the base directory.
        """
        baseDirectory = FilePath(self.mktemp())
        for version in versions:
            self.makeProject(version, baseDirectory)
        return baseDirectory


    def test_getVersion(self):
        """
        Project objects know their version.
        """
        version = Version('twisted', 2, 1, 0)
        project = self.makeProject(version)
        self.assertEqual(project.getVersion(), version)


    def test_updateVersion(self):
        """
        Project objects know how to update the version numbers in those
        projects.
        """
        project = self.makeProject(Version("twisted", 2, 1, 0))
        newVersion = Version("twisted", 3, 2, 9)
        project.updateVersion(newVersion)
        self.assertEqual(project.getVersion(), newVersion)
        self.assertEqual(
            project.directory.child("topfiles").child("README").getContent(),
            "3.2.9")


    def test_repr(self):
        """
        The representation of a Project is Project(directory).
        """
        foo = Project(FilePath('bar'))
        self.assertEqual(
            repr(foo), 'Project(%r)' % (foo.directory))


    def test_findTwistedStyleProjects(self):
        """
        findTwistedStyleProjects finds all projects underneath a particular
        directory. A 'project' is defined by the existence of a 'topfiles'
        directory and is returned as a Project object.
        """
        baseDirectory = self.makeProjects(
            Version('foo', 2, 3, 0), Version('foo.bar', 0, 7, 4))
        projects = findTwistedProjects(baseDirectory)
        self.assertProjectsEqual(
            projects,
            [Project(baseDirectory.child('foo')),
             Project(baseDirectory.child('foo').child('bar'))])



class UtilityTests(ExternalTempdirTestCase):
    """
    Tests for various utility functions for releasing.
    """

    def test_chdir(self):
        """
        Test that the runChdirSafe is actually safe, i.e., it still
        changes back to the original directory even if an error is
        raised.
        """
        cwd = os.getcwd()

        def chAndBreak():
            os.mkdir('releaseCh')
            os.chdir('releaseCh')
            1 // 0

        self.assertRaises(ZeroDivisionError,
                          release.runChdirSafe, chAndBreak)
        self.assertEqual(cwd, os.getcwd())



    def test_replaceInFile(self):
        """
        L{replaceInFile} replaces data in a file based on a dict. A key from
        the dict that is found in the file is replaced with the corresponding
        value.
        """
        content = 'foo\nhey hey $VER\nbar\n'
        with open('release.replace', 'w') as outf:
            outf.write(content)

        expected = content.replace('$VER', '2.0.0')
        replaceInFile('release.replace', {'$VER': '2.0.0'})
        with open('release.replace') as f:
            self.assertEqual(f.read(), expected)


        expected = expected.replace('2.0.0', '3.0.0')
        replaceInFile('release.replace', {'2.0.0': '3.0.0'})
        with open('release.replace') as f:
            self.assertEqual(f.read(), expected)



class VersionWritingTests(ExternalTempdirTestCase):
    """
    Tests for L{replaceProjectVersion}.
    """

    def test_replaceProjectVersion(self):
        """
        L{replaceProjectVersion} writes a Python file that defines a
        C{version} variable that corresponds to the given name and version
        number.
        """
        replaceProjectVersion("test_project",
                              Version("twisted.test_project", 0, 82, 7))
        ns = {'__name___': 'twisted.test_project'}
        execfile("test_project", ns)
        self.assertEqual(ns["version"].base(), "0.82.7")


    def test_replaceProjectVersionWithPrerelease(self):
        """
        L{replaceProjectVersion} will write a Version instantiation that
        includes a prerelease parameter if necessary.
        """
        replaceProjectVersion("test_project",
                              Version("twisted.test_project", 0, 82, 7,
                                      prerelease=8))
        ns = {'__name___': 'twisted.test_project'}
        execfile("test_project", ns)
        self.assertEqual(ns["version"].base(), "0.82.7pre8")



class APIBuilderTests(ExternalTempdirTestCase):
    """
    Tests for L{APIBuilder}.
    """
    skip = pydoctorSkip

    def test_build(self):
        """
        L{APIBuilder.build} writes an index file which includes the name of the
        project specified.
        """
        stdout = StringIO()
        self.patch(sys, 'stdout', stdout)

        projectName = "Foobar"
        packageName = "quux"
        projectURL = "scheme:project"
        sourceURL = "scheme:source"
        docstring = "text in docstring"
        privateDocstring = "should also appear in output"

        inputPath = FilePath(self.mktemp()).child(packageName)
        inputPath.makedirs()
        inputPath.child("__init__.py").setContent(
            "def foo():\n"
            "    '%s'\n"
            "def _bar():\n"
            "    '%s'" % (docstring, privateDocstring))

        outputPath = FilePath(self.mktemp())

        builder = APIBuilder()
        builder.build(projectName, projectURL, sourceURL, inputPath,
                      outputPath)

        indexPath = outputPath.child("index.html")

        self.assertTrue(
            indexPath.exists(),
            "API index %r did not exist." % (outputPath.path,))
        self.assertIn(
            '<a href="%s">%s</a>' % (projectURL, projectName),
            indexPath.getContent(),
            "Project name/location not in file contents.")

        quuxPath = outputPath.child("quux.html")
        self.assertTrue(
            quuxPath.exists(),
            "Package documentation file %r did not exist." % (quuxPath.path,))
        self.assertIn(
            docstring, quuxPath.getContent(),
            "Docstring not in package documentation file.")
        self.assertIn(
            '<a href="%s/%s">View Source</a>' % (sourceURL, packageName),
            quuxPath.getContent())
        self.assertIn(
            '<a class="functionSourceLink" href="%s/%s/__init__.py#L1">' % (
                sourceURL, packageName),
            quuxPath.getContent())
        self.assertIn(privateDocstring, quuxPath.getContent())

        # There should also be a page for the foo function in quux.
        self.assertTrue(quuxPath.sibling('quux.foo.html').exists())

        self.assertEqual(stdout.getvalue(), '')


    def test_buildWithPolicy(self):
        """
        L{BuildAPIDocsScript.buildAPIDocs} builds the API docs with values
        appropriate for the Twisted project.
        """
        stdout = StringIO()
        self.patch(sys, 'stdout', stdout)
        docstring = "text in docstring"

        projectRoot = FilePath(self.mktemp())
        packagePath = projectRoot.child("twisted")
        packagePath.makedirs()
        packagePath.child("__init__.py").setContent(
            "def foo():\n"
            "    '%s'\n" % (docstring,))
        packagePath.child("_version.py").setContent(
            genVersion("twisted", 1, 0, 0))
        outputPath = FilePath(self.mktemp())

        script = BuildAPIDocsScript()
        script.buildAPIDocs(projectRoot, outputPath)

        indexPath = outputPath.child("index.html")
        self.assertTrue(
            indexPath.exists(),
            "API index %r did not exist." % (outputPath.path,))
        self.assertIn(
            '<a href="http://twistedmatrix.com/">Twisted</a>',
            indexPath.getContent(),
            "Project name/location not in file contents.")

        twistedPath = outputPath.child("twisted.html")
        self.assertTrue(
            twistedPath.exists(),
            "Package documentation file %r did not exist."
            % (twistedPath.path,))
        self.assertIn(
            docstring, twistedPath.getContent(),
            "Docstring not in package documentation file.")
        #Here we check that it figured out the correct version based on the
        #source code.
        self.assertIn(
            '<a href="https://github.com/twisted/twisted/tree/'
            'twisted-1.0.0/twisted">View Source</a>',
            twistedPath.getContent())

        self.assertEqual(stdout.getvalue(), '')


    def test_buildWithDeprecated(self):
        """
        The templates and System for Twisted includes adding deprecations.
        """
        stdout = StringIO()
        self.patch(sys, 'stdout', stdout)

        projectName = "Foobar"
        packageName = "quux"
        projectURL = "scheme:project"
        sourceURL = "scheme:source"
        docstring = "text in docstring"
        privateDocstring = "should also appear in output"

        inputPath = FilePath(self.mktemp()).child(packageName)
        inputPath.makedirs()
        inputPath.child("__init__.py").setContent(
            "from twisted.python.deprecate import deprecated\n"
            "from twisted.python.versions import Version\n"
            "@deprecated(Version('Twisted', 15, 0, 0), "
            "'Baz')\n"
            "def foo():\n"
            "    '%s'\n"
            "from twisted.python import deprecate, versions\n"
            "@deprecate.deprecated(versions.Version('Twisted', 16, 0, 0))\n"
            "def _bar():\n"
            "    '%s'\n"
            "@deprecated(Version('Twisted', 14, 2, 3), replacement='stuff')\n"
            "class Baz(object):\n"
            "    pass"
            "" % (docstring, privateDocstring))

        outputPath = FilePath(self.mktemp())

        builder = APIBuilder()
        builder.build(projectName, projectURL, sourceURL, inputPath,
                      outputPath)

        quuxPath = outputPath.child("quux.html")
        self.assertTrue(
            quuxPath.exists(),
            "Package documentation file %r did not exist." % (quuxPath.path,))
        self.assertIn(
            docstring, quuxPath.getContent(),
            "Docstring not in package documentation file.")
        self.assertIn(
            'foo was deprecated in Twisted 15.0.0; please use Baz instead.',
            quuxPath.getContent())
        self.assertIn(
            '_bar was deprecated in Twisted 16.0.0.',
            quuxPath.getContent())
        self.assertIn(privateDocstring, quuxPath.getContent())

        # There should also be a page for the foo function in quux.
        self.assertTrue(quuxPath.sibling('quux.foo.html').exists())

        self.assertIn(
            'foo was deprecated in Twisted 15.0.0; please use Baz instead.',
            quuxPath.sibling('quux.foo.html').getContent())

        self.assertIn(
            'Baz was deprecated in Twisted 14.2.3; please use stuff instead.',
            quuxPath.sibling('quux.Baz.html').getContent())


        self.assertEqual(stdout.getvalue(), '')


    def test_apiBuilderScriptMainRequiresTwoArguments(self):
        """
        SystemExit is raised when the incorrect number of command line
        arguments are passed to the API building script.
        """
        script = BuildAPIDocsScript()
        self.assertRaises(SystemExit, script.main, [])
        self.assertRaises(SystemExit, script.main, ["foo"])
        self.assertRaises(SystemExit, script.main, ["foo", "bar", "baz"])


    def test_apiBuilderScriptMain(self):
        """
        The API building script invokes the same code that
        L{test_buildWithPolicy} tests.
        """
        script = BuildAPIDocsScript()
        calls = []
        script.buildAPIDocs = lambda a, b: calls.append((a, b))
        script.main(["hello", "there"])
        self.assertEqual(calls, [(FilePath("hello"), FilePath("there"))])



class FilePathDeltaTests(TestCase):
    """
    Tests for L{filePathDelta}.
    """

    def test_filePathDeltaSubdir(self):
        """
        L{filePathDelta} can create a simple relative path to a child path.
        """
        self.assertEqual(filePathDelta(FilePath("/foo/bar"),
                                       FilePath("/foo/bar/baz")),
                         ["baz"])


    def test_filePathDeltaSiblingDir(self):
        """
        L{filePathDelta} can traverse upwards to create relative paths to
        siblings.
        """
        self.assertEqual(filePathDelta(FilePath("/foo/bar"),
                                       FilePath("/foo/baz")),
                         ["..", "baz"])


    def test_filePathNoCommonElements(self):
        """
        L{filePathDelta} can create relative paths to totally unrelated paths
        for maximum portability.
        """
        self.assertEqual(filePathDelta(FilePath("/foo/bar"),
                                       FilePath("/baz/quux")),
                         ["..", "..", "baz", "quux"])


    def test_filePathDeltaSimilarEndElements(self):
        """
        L{filePathDelta} doesn't take into account final elements when
        comparing 2 paths, but stops at the first difference.
        """
        self.assertEqual(filePathDelta(FilePath("/foo/bar/bar/spam"),
                                       FilePath("/foo/bar/baz/spam")),
                         ["..", "..", "baz", "spam"])



class NewsBuilderMixin(StructureAssertingMixin):
    """
    Tests for L{NewsBuilder} using Git.
    """

    def setUp(self):
        """
        Create a fake project and stuff some basic structure and content into
        it.
        """
        self.builder = NewsBuilder()
        self.project = FilePath(self.mktemp())

        self.existingText = 'Here is stuff which was present previously.\n'
        self.createStructure(
            self.project, {
                'NEWS': self.existingText,
                '5.feature': 'We now support the web.\n',
                '12.feature': 'The widget is more robust.\n',
                '15.feature': (
                    'A very long feature which takes many words to '
                    'describe with any accuracy was introduced so that '
                    'the line wrapping behavior of the news generating '
                    'code could be verified.\n'),
                '16.feature': (
                    'A simpler feature\ndescribed on multiple lines\n'
                    'was added.\n'),
                '23.bugfix': 'Broken stuff was fixed.\n',
                '25.removal': 'Stupid stuff was deprecated.\n',
                '30.misc': '',
                '35.misc': '',
                '40.doc': 'foo.bar.Baz.quux',
                '41.doc': 'writing Foo servers'})


    def test_today(self):
        """
        L{NewsBuilder._today} returns today's date in YYYY-MM-DD form.
        """
        self.assertEqual(
            self.builder._today(), date.today().strftime('%Y-%m-%d'))


    def test_findFeatures(self):
        """
        When called with L{NewsBuilder._FEATURE}, L{NewsBuilder._findChanges}
        returns a list of bugfix ticket numbers and descriptions as a list of
        two-tuples.
        """
        features = self.builder._findChanges(
            self.project, self.builder._FEATURE)
        self.assertEqual(
            features,
            [(5, "We now support the web."),
             (12, "The widget is more robust."),
             (15,
              "A very long feature which takes many words to describe with "
              "any accuracy was introduced so that the line wrapping behavior "
              "of the news generating code could be verified."),
             (16, "A simpler feature described on multiple lines was added.")])


    def test_findBugfixes(self):
        """
        When called with L{NewsBuilder._BUGFIX}, L{NewsBuilder._findChanges}
        returns a list of bugfix ticket numbers and descriptions as a list of
        two-tuples.
        """
        bugfixes = self.builder._findChanges(
            self.project, self.builder._BUGFIX)
        self.assertEqual(
            bugfixes,
            [(23, 'Broken stuff was fixed.')])


    def test_findRemovals(self):
        """
        When called with L{NewsBuilder._REMOVAL}, L{NewsBuilder._findChanges}
        returns a list of removal/deprecation ticket numbers and descriptions
        as a list of two-tuples.
        """
        removals = self.builder._findChanges(
            self.project, self.builder._REMOVAL)
        self.assertEqual(
            removals,
            [(25, 'Stupid stuff was deprecated.')])


    def test_findDocumentation(self):
        """
        When called with L{NewsBuilder._DOC}, L{NewsBuilder._findChanges}
        returns a list of documentation ticket numbers and descriptions as a
        list of two-tuples.
        """
        doc = self.builder._findChanges(
            self.project, self.builder._DOC)
        self.assertEqual(
            doc,
            [(40, 'foo.bar.Baz.quux'),
             (41, 'writing Foo servers')])


    def test_findMiscellaneous(self):
        """
        When called with L{NewsBuilder._MISC}, L{NewsBuilder._findChanges}
        returns a list of removal/deprecation ticket numbers and descriptions
        as a list of two-tuples.
        """
        misc = self.builder._findChanges(
            self.project, self.builder._MISC)
        self.assertEqual(
            misc,
            [(30, ''),
             (35, '')])


    def test_writeHeader(self):
        """
        L{NewsBuilder._writeHeader} accepts a file-like object opened for
        writing and a header string and writes out a news file header to it.
        """
        output = StringIO()
        self.builder._writeHeader(output, "Super Awesometastic 32.16")
        self.assertEqual(
            output.getvalue(),
            "Super Awesometastic 32.16\n"
            "=========================\n"
            "\n")


    def test_writeSection(self):
        """
        L{NewsBuilder._writeSection} accepts a file-like object opened for
        writing, a section name, and a list of ticket information (as returned
        by L{NewsBuilder._findChanges}) and writes out a section header and all
        of the given ticket information.
        """
        output = StringIO()
        self.builder._writeSection(
            output, "Features",
            [(3, "Great stuff."),
             (17, "Very long line which goes on and on and on, seemingly "
              "without end until suddenly without warning it does end.")])
        self.assertEqual(
            output.getvalue(),
            "Features\n"
            "--------\n"
            " - Great stuff. (#3)\n"
            " - Very long line which goes on and on and on, seemingly "
            "without end\n"
            "   until suddenly without warning it does end. (#17)\n"
            "\n")


    def test_writeMisc(self):
        """
        L{NewsBuilder._writeMisc} accepts a file-like object opened for
        writing, a section name, and a list of ticket information (as returned
        by L{NewsBuilder._findChanges} and writes out a section header and all
        of the ticket numbers, but excludes any descriptions.
        """
        output = StringIO()
        self.builder._writeMisc(
            output, "Other",
            [(x, "") for x in range(2, 50, 3)])
        self.assertEqual(
            output.getvalue(),
            "Other\n"
            "-----\n"
            " - #2, #5, #8, #11, #14, #17, #20, #23, #26, #29, #32, #35, "
            "#38, #41,\n"
            "   #44, #47\n"
            "\n")


    def test_build(self):
        """
        L{NewsBuilder.build} updates a NEWS file with new features based on the
        I{<ticket>.feature} files found in the directory specified.
        """
        self.builder.build(
            self.project, self.project.child('NEWS'),
            "Super Awesometastic 32.16")

        results = self.project.child('NEWS').getContent()
        self.assertEqual(
            results,
            'Super Awesometastic 32.16\n'
            '=========================\n'
            '\n'
            'Features\n'
            '--------\n'
            ' - We now support the web. (#5)\n'
            ' - The widget is more robust. (#12)\n'
            ' - A very long feature which takes many words to describe '
            'with any\n'
            '   accuracy was introduced so that the line wrapping behavior '
            'of the\n'
            '   news generating code could be verified. (#15)\n'
            ' - A simpler feature described on multiple lines was '
            'added. (#16)\n'
            '\n'
            'Bugfixes\n'
            '--------\n'
            ' - Broken stuff was fixed. (#23)\n'
            '\n'
            'Improved Documentation\n'
            '----------------------\n'
            ' - foo.bar.Baz.quux (#40)\n'
            ' - writing Foo servers (#41)\n'
            '\n'
            'Deprecations and Removals\n'
            '-------------------------\n'
            ' - Stupid stuff was deprecated. (#25)\n'
            '\n'
            'Other\n'
            '-----\n'
            ' - #30, #35\n'
            '\n\n' + self.existingText)


    def test_emptyProjectCalledOut(self):
        """
        If no changes exist for a project, I{NEWS} gains a new section for
        that project that includes some helpful text about how there were no
        interesting changes.
        """
        project = FilePath(self.mktemp()).child("twisted")
        project.makedirs()
        self.createStructure(project, {'NEWS': self.existingText})

        self.builder.build(
            project, project.child('NEWS'),
            "Super Awesometastic 32.16")
        results = project.child('NEWS').getContent()
        self.assertEqual(
            results,
            'Super Awesometastic 32.16\n'
            '=========================\n'
            '\n' +
            self.builder._NO_CHANGES +
            '\n\n' + self.existingText)


    def test_preserveTicketHint(self):
        """
        If a I{NEWS} file begins with the two magic lines which point readers
        at the issue tracker, those lines are kept at the top of the new file.
        """
        news = self.project.child('NEWS')
        news.setContent(
            'Ticket numbers in this file can be looked up by visiting\n'
            'http://twistedmatrix.com/trac/ticket/<number>\n'
            '\n'
            'Blah blah other stuff.\n')

        self.builder.build(self.project, news, "Super Awesometastic 32.16")

        self.assertEqual(
            news.getContent(),
            'Ticket numbers in this file can be looked up by visiting\n'
            'http://twistedmatrix.com/trac/ticket/<number>\n'
            '\n'
            'Super Awesometastic 32.16\n'
            '=========================\n'
            '\n'
            'Features\n'
            '--------\n'
            ' - We now support the web. (#5)\n'
            ' - The widget is more robust. (#12)\n'
            ' - A very long feature which takes many words to describe '
            'with any\n'
            '   accuracy was introduced so that the line wrapping behavior '
            'of the\n'
            '   news generating code could be verified. (#15)\n'
            ' - A simpler feature described on multiple lines was '
            'added. (#16)\n'
            '\n'
            'Bugfixes\n'
            '--------\n'
            ' - Broken stuff was fixed. (#23)\n'
            '\n'
            'Improved Documentation\n'
            '----------------------\n'
            ' - foo.bar.Baz.quux (#40)\n'
            ' - writing Foo servers (#41)\n'
            '\n'
            'Deprecations and Removals\n'
            '-------------------------\n'
            ' - Stupid stuff was deprecated. (#25)\n'
            '\n'
            'Other\n'
            '-----\n'
            ' - #30, #35\n'
            '\n\n'
            'Blah blah other stuff.\n')


    def test_emptySectionsOmitted(self):
        """
        If there are no changes of a particular type (feature, bugfix, etc), no
        section for that type is written by L{NewsBuilder.build}.
        """
        for ticket in self.project.children():
            if ticket.splitext()[1] in ('.feature', '.misc', '.doc'):
                ticket.remove()

        self.builder.build(
            self.project, self.project.child('NEWS'),
            'Some Thing 1.2')

        self.assertEqual(
            self.project.child('NEWS').getContent(),
            'Some Thing 1.2\n'
            '==============\n'
            '\n'
            'Bugfixes\n'
            '--------\n'
            ' - Broken stuff was fixed. (#23)\n'
            '\n'
            'Deprecations and Removals\n'
            '-------------------------\n'
            ' - Stupid stuff was deprecated. (#25)\n'
            '\n\n'
            'Here is stuff which was present previously.\n')


    def test_duplicatesMerged(self):
        """
        If two change files have the same contents, they are merged in the
        generated news entry.
        """
        def feature(s):
            return self.project.child(s + '.feature')
        feature('5').copyTo(feature('15'))
        feature('5').copyTo(feature('16'))

        self.builder.build(
            self.project, self.project.child('NEWS'),
            'Project Name 5.0')

        self.assertEqual(
            self.project.child('NEWS').getContent(),
            'Project Name 5.0\n'
            '================\n'
            '\n'
            'Features\n'
            '--------\n'
            ' - We now support the web. (#5, #15, #16)\n'
            ' - The widget is more robust. (#12)\n'
            '\n'
            'Bugfixes\n'
            '--------\n'
            ' - Broken stuff was fixed. (#23)\n'
            '\n'
            'Improved Documentation\n'
            '----------------------\n'
            ' - foo.bar.Baz.quux (#40)\n'
            ' - writing Foo servers (#41)\n'
            '\n'
            'Deprecations and Removals\n'
            '-------------------------\n'
            ' - Stupid stuff was deprecated. (#25)\n'
            '\n'
            'Other\n'
            '-----\n'
            ' - #30, #35\n'
            '\n\n'
            'Here is stuff which was present previously.\n')


    def createFakeTwistedProject(self):
        """
        Create a fake-looking Twisted project to build from.
        """
        project = FilePath(self.mktemp()).child("twisted")
        project.makedirs()
        self.createStructure(
            project, {
                'NEWS': 'Old boring stuff from the past.\n',
                '_version.py': genVersion("twisted", 1, 2, 3),
                'topfiles': {
                    'NEWS': 'Old core news.\n',
                    '3.feature': 'Third feature addition.\n',
                    '5.misc': ''},
                'conch': {
                    '_version.py': genVersion("twisted.conch", 3, 4, 5),
                    'topfiles': {
                        'NEWS': 'Old conch news.\n',
                        '7.bugfix': 'Fixed that bug.\n'}}})
        return project


    def test_buildAll(self):
        """
        L{NewsBuilder.buildAll} calls L{NewsBuilder.build} once for each
        subproject, passing that subproject's I{topfiles} directory as C{path},
        the I{NEWS} file in that directory as C{output}, and the subproject's
        name as C{header}, and then again for each subproject with the
        top-level I{NEWS} file for C{output}. Blacklisted subprojects are
        skipped.
        """
        builds = []
        builder = NewsBuilder()
        builder.build = lambda path, output, header: builds.append((
            path, output, header))
        builder._today = lambda: '2009-12-01'

        self.project = self.createFakeTwistedProject()
        self._commit(self.project)
        builder.buildAll(self.project)

        coreTopfiles = self.project.child("topfiles")
        coreNews = coreTopfiles.child("NEWS")
        coreHeader = "Twisted Core 1.2.3 (2009-12-01)"

        conchTopfiles = self.project.child("conch").child("topfiles")
        conchNews = conchTopfiles.child("NEWS")
        conchHeader = "Twisted Conch 1.2.3 (2009-12-01)"

        aggregateNews = self.project.child("NEWS")

        self.assertEqual(
            builds,
            [(conchTopfiles, conchNews, conchHeader),
             (conchTopfiles, aggregateNews, conchHeader),
             (coreTopfiles, coreNews, coreHeader),
             (coreTopfiles, aggregateNews, coreHeader)])


    def test_buildAllAggregate(self):
        """
        L{NewsBuilder.buildAll} aggregates I{NEWS} information into the top
        files, only deleting fragments once it's done.
        """
        builder = NewsBuilder()
        project = self.createFakeTwistedProject()
        self._commit(project)
        builder.buildAll(project)

        aggregateNews = project.child("NEWS")

        aggregateContent = aggregateNews.getContent()
        self.assertIn("Third feature addition", aggregateContent)
        self.assertIn("Fixed that bug", aggregateContent)
        self.assertIn("Old boring stuff from the past", aggregateContent)


    def test_changeVersionInNews(self):
        """
        L{NewsBuilder._changeVersions} gets the release date for a given
        version of a project as a string.
        """
        builder = NewsBuilder()
        builder._today = lambda: '2009-12-01'
        project = self.createFakeTwistedProject()
        self._commit(project)
        builder.buildAll(project)
        newVersion = Version('TEMPLATE', 7, 7, 14)
        coreNews = project.child('topfiles').child('NEWS')
        # twisted 1.2.3 is the old version.
        builder._changeNewsVersion(
            coreNews, "Core", Version("twisted", 1, 2, 3),
            newVersion, '2010-01-01')
        expectedCore = (
            'Twisted Core 7.7.14 (2010-01-01)\n'
            '================================\n'
            '\n'
            'Features\n'
            '--------\n'
            ' - Third feature addition. (#3)\n'
            '\n'
            'Other\n'
            '-----\n'
            ' - #5\n\n\n')
        self.assertEqual(
            expectedCore + 'Old core news.\n', coreNews.getContent())


    def test_removeNEWSfragments(self):
        """
        L{NewsBuilder.buildALL} removes all the NEWS fragments after the build
        process, using the VCS's C{rm} command.
        """
        builder = NewsBuilder()
        project = self.createFakeTwistedProject()
        self._commit(project)
        builder.buildAll(project)

        self.assertEqual(5, len(project.children()))
        output = self._getStatus(project)
        removed = [line for line in output.splitlines()
                   if line.startswith("D ")]
        self.assertEqual(3, len(removed))


    def test_checkRepo(self):
        """
        L{NewsBuilder.buildAll} raises L{NotWorkingDirectory} when the given
        path is not a supported repository.
        """
        self.assertRaises(
            NotWorkingDirectory, self.builder.buildAll, self.project)


class NewsBuilderGitTests(NewsBuilderMixin, ExternalTempdirTestCase):
    """
    Tests for L{NewsBuilder} using Git.
    """
    skip = gitSkip

    def _commit(self, project=None):
        """
        Make the C{project} directory a valid Git repository with all
        files committed.
        """
        if project is None:
            project = self.project

        _gitInit(project)
        runCommand(["git", "-C", project.path, "add"] + glob.glob(
            project.path + "/*"))
        runCommand(["git", "-C", project.path, "commit", "-m", "yay"])

    def _getStatus(self, project):
        return runCommand(["git", "-C", project.path, "status", "--short"])



class SphinxBuilderTests(TestCase):
    """
    Tests for L{SphinxBuilder}.

    @note: This test case depends on twisted.web, which violates the standard
        Twisted practice of not having anything in twisted.python depend on
        other Twisted packages and opens up the possibility of creating
        circular dependencies.  Do not use this as an example of how to
        structure your dependencies.

    @ivar builder: A plain L{SphinxBuilder}.

    @ivar sphinxDir: A L{FilePath} representing a directory to be used for
        containing a Sphinx project.

    @ivar sourceDir: A L{FilePath} representing a directory to be used for
        containing the source files for a Sphinx project.
    """
    skip = sphinxSkip

    confContent = """\
                  source_suffix = '.rst'
                  master_doc = 'index'
                  """
    confContent = textwrap.dedent(confContent)

    indexContent = """\
                   ==============
                   This is a Test
                   ==============

                   This is only a test
                   -------------------

                   In case you hadn't figured it out yet, this is a test.
                   """
    indexContent = textwrap.dedent(indexContent)


    def setUp(self):
        """
        Set up a few instance variables that will be useful.
        """
        self.builder = SphinxBuilder()

        # set up a place for a fake sphinx project
        self.twistedRootDir = FilePath(self.mktemp())
        self.sphinxDir = self.twistedRootDir.child("docs")
        self.sphinxDir.makedirs()
        self.sourceDir = self.sphinxDir


    def createFakeSphinxProject(self):
        """
        Create a fake Sphinx project for test purposes.

        Creates a fake Sphinx project with the absolute minimum of source
        files.  This includes a single source file ('index.rst') and the
        smallest 'conf.py' file possible in order to find that source file.
        """
        self.sourceDir.child("conf.py").setContent(self.confContent)
        self.sourceDir.child("index.rst").setContent(self.indexContent)


    def verifyFileExists(self, fileDir, fileName):
        """
        Helper which verifies that C{fileName} exists in C{fileDir} and it has
        some content.

        @param fileDir: A path to a directory.
        @type fileDir: L{FilePath}

        @param fileName: The last path segment of a file which may exist within
            C{fileDir}.
        @type fileName: L{str}

        @raise: L{FailTest <twisted.trial.unittest.FailTest>} if
            C{fileDir.child(fileName)}:

                1. Does not exist.

                2. Is empty.

                3. In the case where it's a path to a C{.html} file, the
                   content looks like an HTML file.

        @return: L{None}
        """
        # check that file exists
        fpath = fileDir.child(fileName)
        self.assertTrue(fpath.exists())

        # check that the output files have some content
        fcontents = fpath.getContent()
        self.assertTrue(len(fcontents) > 0)

        # check that the html files are at least html-ish
        # this is not a terribly rigorous check
        if fpath.path.endswith('.html'):
            self.assertIn("<body", fcontents)


    def test_build(self):
        """
        Creates and builds a fake Sphinx project using a L{SphinxBuilder}.
        """
        self.createFakeSphinxProject()
        self.builder.build(self.sphinxDir)
        self.verifyBuilt()


    def test_main(self):
        """
        Creates and builds a fake Sphinx project as if via the command line.
        """
        self.createFakeSphinxProject()
        self.builder.main([self.sphinxDir.parent().path])
        self.verifyBuilt()


    def test_warningsAreErrors(self):
        """
        Creates and builds a fake Sphinx project as if via the command line,
        failing if there are any warnings.
        """
        output = StringIO()
        self.patch(sys, "stdout", output)
        self.createFakeSphinxProject()
        with self.sphinxDir.child("index.rst").open("a") as f:
            f.write("\n.. _malformed-link-target\n")
        exception = self.assertRaises(
            SystemExit,
            self.builder.main, [self.sphinxDir.parent().path]
        )
        self.assertEqual(exception.code, 1)
        self.assertIn("malformed hyperlink target", output.getvalue())
        self.verifyBuilt()


    def verifyBuilt(self):
        """
        Verify that a sphinx project has been built.
        """
        htmlDir = self.sphinxDir.sibling('doc')
        self.assertTrue(htmlDir.isdir())
        doctreeDir = htmlDir.child("doctrees")
        self.assertFalse(doctreeDir.exists())

        self.verifyFileExists(htmlDir, 'index.html')
        self.verifyFileExists(htmlDir, 'genindex.html')
        self.verifyFileExists(htmlDir, 'objects.inv')
        self.verifyFileExists(htmlDir, 'search.html')
        self.verifyFileExists(htmlDir, 'searchindex.js')


    def test_failToBuild(self):
        """
        Check that SphinxBuilder.build fails when run against a non-sphinx
        directory.
        """
        # note no fake sphinx project is created
        self.assertRaises(CalledProcessError,
                          self.builder.build,
                          self.sphinxDir)



class ScriptTests(StructureAssertingMixin, ExternalTempdirTestCase):
    """
    Tests for the release script functionality.
    """

    def _testVersionChanging(self, prerelease, patch):
        """
        Check that L{ChangeVersionsScript.main} calls the version-changing
        function with the appropriate version data and filesystem path.
        """
        versionUpdates = []

        def myVersionChanger(sourceTree, prerelease, patch):
            versionUpdates.append((sourceTree, prerelease, patch))

        versionChanger = ChangeVersionsScript()
        versionChanger.changeAllProjectVersions = myVersionChanger
        args = []
        if prerelease:
            args.append("--prerelease")
        if patch:
            args.append("--patch")
        versionChanger.main(args)
        self.assertEqual(len(versionUpdates), 1)
        self.assertEqual(versionUpdates[0][0], FilePath("."))
        self.assertEqual(versionUpdates[0][1], prerelease)
        self.assertEqual(versionUpdates[0][2], patch)


    def test_changeVersions(self):
        """
        L{ChangeVersionsScript.main} changes version numbers for all Twisted
        projects.
        """
        self._testVersionChanging(False, False)


    def test_changeVersionsWithPrerelease(self):
        """
        A prerelease can be created with L{changeVersionsScript}.
        """
        self._testVersionChanging(True, False)


    def test_changeVersionsWithPatch(self):
        """
        A patch release can be created with L{changeVersionsScript}.
        """
        self._testVersionChanging(False, True)


    def test_defaultChangeVersionsVersionChanger(self):
        """
        The default implementation of C{changeAllProjectVersions} is
        L{changeAllProjectVersions}.
        """
        versionChanger = ChangeVersionsScript()
        self.assertEqual(versionChanger.changeAllProjectVersions,
                         changeAllProjectVersions)


    def test_badNumberOfArgumentsToChangeVersionsScript(self):
        """
        L{changeVersionsScript} raises SystemExit when the wrong arguments are
        passed.
        """
        versionChanger = ChangeVersionsScript()
        self.assertRaises(SystemExit, versionChanger.main, ["12.3.0"])


    def test_tooManyDotsToChangeVersionsScript(self):
        """
        L{changeVersionsScript} raises SystemExit when there are the wrong
        number of segments in the version number passed.
        """
        versionChanger = ChangeVersionsScript()
        self.assertRaises(SystemExit, versionChanger.main,
                          ["3.2.1.0"])


    def test_nonIntPartsToChangeVersionsScript(self):
        """
        L{changeVersionsScript} raises SystemExit when the version number isn't
        made out of numbers.
        """
        versionChanger = ChangeVersionsScript()
        self.assertRaises(SystemExit, versionChanger.main,
                          ["my united.states.of prewhatever"])


    def test_badNumberOfArgumentsToBuildNews(self):
        """
        L{NewsBuilder.main} raises L{SystemExit} when other than 1 argument is
        passed to it.
        """
        newsBuilder = NewsBuilder()
        self.assertRaises(SystemExit, newsBuilder.main, [])
        self.assertRaises(SystemExit, newsBuilder.main, ["hello", "world"])


    def test_buildNews(self):
        """
        L{NewsBuilder.main} calls L{NewsBuilder.buildAll} with a L{FilePath}
        instance constructed from the path passed to it.
        """
        builds = []
        newsBuilder = NewsBuilder()
        newsBuilder.buildAll = builds.append
        newsBuilder.main(["/foo/bar/baz"])
        self.assertEqual(builds, [FilePath("/foo/bar/baz")])



class CommandsTestMixin(StructureAssertingMixin):
    """
    Test mixin for the VCS commands used by the release scripts.
    """
    def setUp(self):
        self.tmpDir = FilePath(self.mktemp())


    def test_ensureIsWorkingDirectoryWithWorkingDirectory(self):
        """
        Calling the C{ensureIsWorkingDirectory} VCS command's method on a valid
        working directory doesn't produce any error.
        """
        reposDir = self.makeRepository(self.tmpDir)
        self.assertIsNone(
                         self.createCommand.ensureIsWorkingDirectory(reposDir))


    def test_ensureIsWorkingDirectoryWithNonWorkingDirectory(self):
        """
        Calling the C{ensureIsWorkingDirectory} VCS command's method on an
        invalid working directory raises a L{NotWorkingDirectory} exception.
        """
        self.assertRaises(NotWorkingDirectory,
                          self.createCommand.ensureIsWorkingDirectory,
                          self.tmpDir)


    def test_statusClean(self):
        """
        Calling the C{isStatusClean} VCS command's method on a repository with
        no pending modifications returns C{True}.
        """
        reposDir = self.makeRepository(self.tmpDir)
        self.assertTrue(self.createCommand.isStatusClean(reposDir))


    def test_statusNotClean(self):
        """
        Calling the C{isStatusClean} VCS command's method on a repository with
        no pending modifications returns C{False}.
        """
        reposDir = self.makeRepository(self.tmpDir)
        reposDir.child('some-file').setContent("something")
        self.assertFalse(self.createCommand.isStatusClean(reposDir))


    def test_remove(self):
        """
        Calling the C{remove} VCS command's method remove the specified path
        from the directory.
        """
        reposDir = self.makeRepository(self.tmpDir)
        testFile = reposDir.child('some-file')
        testFile.setContent("something")
        self.commitRepository(reposDir)
        self.assertTrue(testFile.exists())

        self.createCommand.remove(testFile)
        testFile.restat(False) # Refresh the file information
        self.assertFalse(testFile.exists(), "File still exists")


    def test_export(self):
        """
        The C{exportTo} VCS command's method export the content of the
        repository as identical in a specified directory.
        """
        structure = {
            "README.rst": "Hi this is 1.0.0.",
            "twisted": {
                "topfiles": {
                    "README": "Hi this is 1.0.0"},
                "_version.py": genVersion("twisted", 1, 0, 0),
                "web": {
                    "topfiles": {
                        "README": "Hi this is 1.0.0"},
                    "_version.py": genVersion("twisted.web", 1, 0, 0)}}}
        reposDir = self.makeRepository(self.tmpDir)
        self.createStructure(reposDir, structure)
        self.commitRepository(reposDir)

        exportDir = FilePath(self.mktemp()).child("export")
        self.createCommand.exportTo(reposDir, exportDir)
        self.assertStructure(exportDir, structure)



class GitCommandTest(CommandsTestMixin, ExternalTempdirTestCase):
    """
    Specific L{CommandsTestMixin} related to Git repositories through
    L{GitCommand}.
    """
    createCommand = GitCommand
    skip = gitSkip


    def makeRepository(self, root):
        """
        Create a Git repository in the specified path.

        @type root: L{FilePath}
        @params root: The directory to create the Git repository into.

        @return: The path to the repository just created.
        @rtype: L{FilePath}
        """
        _gitInit(root)
        return root


    def commitRepository(self, repository):
        """
        Add and commit all the files from the Git repository specified.

        @type repository: L{FilePath}
        @params repository: The Git repository to commit into.
        """
        runCommand(["git", "-C", repository.path, "add"] +
                   glob.glob(repository.path + "/*"))
        runCommand(["git", "-C", repository.path, "commit", "-m", "hop"])



class RepositoryCommandDetectionTest(ExternalTempdirTestCase):
    """
    Test the L{getRepositoryCommand} to access the right set of VCS commands
    depending on the repository manipulated.
    """
    skip = gitSkip

    def setUp(self):
        self.repos = FilePath(self.mktemp())


    def test_git(self):
        """
        L{getRepositoryCommand} from a Git repository returns L{GitCommand}.
        """
        _gitInit(self.repos)
        cmd = getRepositoryCommand(self.repos)
        self.assertIs(cmd, GitCommand)


    def test_unknownRepository(self):
        """
        L{getRepositoryCommand} from a directory which doesn't look like a Git
        repository produces a L{NotWorkingDirectory} exception.
        """
        self.assertRaises(NotWorkingDirectory, getRepositoryCommand,
                          self.repos)



class VCSCommandInterfaceTests(TestCase):
    """
    Test that the VCS command classes implement their interface.
    """
    def test_git(self):
        """
        L{GitCommand} implements L{IVCSCommand}.
        """
        self.assertTrue(IVCSCommand.implementedBy(GitCommand))



class CheckTopfileScriptTests(ExternalTempdirTestCase):
    """
    Tests for L{CheckTopfileScript}.
    """
    skip = gitSkip

    def setUp(self):
        self.origin = FilePath(self.mktemp())
        _gitInit(self.origin)
        runCommand(["git", "checkout", "-b", "trunk"],
                   cwd=self.origin.path)
        self.origin.child("test").setContent(b"test!")
        runCommand(["git", "add", self.origin.child("test").path],
                   cwd=self.origin.path)
        runCommand(["git", "commit", "-m", "initial"],
                   cwd=self.origin.path)

        self.repo = FilePath(self.mktemp())

        runCommand(["git", "clone", self.origin.path, self.repo.path])
        _gitConfig(self.repo)


    def test_noArgs(self):
        """
        Too few arguments returns a failure.
        """
        logs = []

        with self.assertRaises(SystemExit) as e:
            CheckTopfileScript(logs.append).main([])

        self.assertEqual(e.exception.args,
                         ("Must specify one argument: the Twisted checkout",))

    def test_diffFromTrunkNoTopfiles(self):
        """
        If there are changes from trunk, then there should also be a topfile.
        """
        runCommand(["git", "checkout", "-b", "mypatch"],
                   cwd=self.repo.path)
        somefile = self.repo.child("somefile")
        somefile.setContent(b"change")

        runCommand(["git", "add", somefile.path, somefile.path],
                   cwd=self.repo.path)
        runCommand(["git", "commit", "-m", "some file"],
                   cwd=self.repo.path)

        logs = []

        with self.assertRaises(SystemExit) as e:
            CheckTopfileScript(logs.append).main([self.repo.path])

        self.assertEqual(e.exception.args, (1,))
        self.assertEqual(logs[-1], "No topfile found. Have you committed it?")


    def test_noChangeFromTrunk(self):
        """
        If there are no changes from trunk, then no need to check the topfiles
        """
        runCommand(["git", "checkout", "-b", "mypatch"],
                   cwd=self.repo.path)

        logs = []

        with self.assertRaises(SystemExit) as e:
            CheckTopfileScript(logs.append).main([self.repo.path])

        self.assertEqual(e.exception.args, (0,))
        self.assertEqual(
            logs[-1],
            "On trunk or no diffs from trunk; no need to look at this.")


    def test_trunk(self):
        """
        Running it on trunk always gives green.
        """
        logs = []

        with self.assertRaises(SystemExit) as e:
            CheckTopfileScript(logs.append).main([self.repo.path])

        self.assertEqual(e.exception.args, (0,))
        self.assertEqual(
            logs[-1],
            "On trunk or no diffs from trunk; no need to look at this.")


    def test_release(self):
        """
        Running it on a release branch returns green if there is no topfiles
        even if there are changes.
        """
        runCommand(["git", "checkout", "-b", "release-16.11111-9001"],
                   cwd=self.repo.path)

        somefile = self.repo.child("somefile")
        somefile.setContent(b"change")

        runCommand(["git", "add", somefile.path, somefile.path],
                   cwd=self.repo.path)
        runCommand(["git", "commit", "-m", "some file"],
                   cwd=self.repo.path)

        logs = []

        with self.assertRaises(SystemExit) as e:
            CheckTopfileScript(logs.append).main([self.repo.path])

        self.assertEqual(e.exception.args, (0,))
        self.assertEqual(logs[-1],
                         "Release branch with no topfiles, all good.")


    def test_releaseWithTopfiles(self):
        """
        Running it on a release branch returns red if there are new topfiles.
        """
        runCommand(["git", "checkout", "-b", "release-16.11111-9001"],
                   cwd=self.repo.path)

        topfiles = self.repo.child("twisted").child("topfiles")
        topfiles.makedirs()
        fragment = topfiles.child("1234.misc")
        fragment.setContent(b"")

        unrelated = self.repo.child("somefile")
        unrelated.setContent(b"Boo")

        runCommand(["git", "add", fragment.path, unrelated.path],
                   cwd=self.repo.path)
        runCommand(["git", "commit", "-m", "fragment"],
                   cwd=self.repo.path)

        logs = []

        with self.assertRaises(SystemExit) as e:
            CheckTopfileScript(logs.append).main([self.repo.path])

        self.assertEqual(e.exception.args, (1,))
        self.assertEqual(logs[-1],
                         "No topfiles should be on the release branch.")


    def test_onlyQuotes(self):
        """
        Running it on a branch with only a quotefile change gives green.
        """
        runCommand(["git", "checkout", "-b", "quotefile"],
                   cwd=self.repo.path)

        fun = self.repo.child("docs").child("fun")
        fun.makedirs()
        quotes = fun.child("Twisted.Quotes")
        quotes.setContent(b"Beep boop")

        runCommand(["git", "add", quotes.path],
                   cwd=self.repo.path)
        runCommand(["git", "commit", "-m", "quotes"],
                   cwd=self.repo.path)

        logs = []

        with self.assertRaises(SystemExit) as e:
            CheckTopfileScript(logs.append).main([self.repo.path])

        self.assertEqual(e.exception.args, (0,))
        self.assertEqual(logs[-1],
                         "Quotes change only; no topfile needed.")


    def test_topfileAdded(self):
        """
        Running it on a branch with a fragment in the topfiles dir added
        returns green.
        """
        runCommand(["git", "checkout", "-b", "quotefile"],
                   cwd=self.repo.path)

        topfiles = self.repo.child("twisted").child("topfiles")
        topfiles.makedirs()
        fragment = topfiles.child("1234.misc")
        fragment.setContent(b"")

        unrelated = self.repo.child("somefile")
        unrelated.setContent(b"Boo")

        runCommand(["git", "add", fragment.path, unrelated.path],
                   cwd=self.repo.path)
        runCommand(["git", "commit", "-m", "topfile"],
                   cwd=self.repo.path)

        logs = []

        with self.assertRaises(SystemExit) as e:
            CheckTopfileScript(logs.append).main([self.repo.path])

        self.assertEqual(e.exception.args, (0,))
        self.assertEqual(logs[-1], "Found twisted/topfiles/1234.misc")


    def test_topfileButNotFragmentAdded(self):
        """
        Running it on a branch with a non-fragment in the topfiles dir does not
        return green.
        """
        runCommand(["git", "checkout", "-b", "quotefile"],
                   cwd=self.repo.path)

        topfiles = self.repo.child("twisted").child("topfiles")
        topfiles.makedirs()
        notFragment = topfiles.child("1234.txt")
        notFragment.setContent(b"")

        unrelated = self.repo.child("somefile")
        unrelated.setContent(b"Boo")

        runCommand(["git", "add", notFragment.path, unrelated.path],
                   cwd=self.repo.path)
        runCommand(["git", "commit", "-m", "not topfile"],
                   cwd=self.repo.path)

        logs = []

        with self.assertRaises(SystemExit) as e:
            CheckTopfileScript(logs.append).main([self.repo.path])

        self.assertEqual(e.exception.args, (1,))
        self.assertEqual(logs[-1], "No topfile found. Have you committed it?")


    def test_topfileAddedButWithOtherTopfiles(self):
        """
        Running it on a branch with a fragment in the topfiles dir added
        returns green, even if there are other files in the topfiles dir.
        """
        runCommand(["git", "checkout", "-b", "quotefile"],
                   cwd=self.repo.path)

        topfiles = self.repo.child("twisted").child("topfiles")
        topfiles.makedirs()
        fragment = topfiles.child("1234.misc")
        fragment.setContent(b"")

        unrelated = topfiles.child("somefile")
        unrelated.setContent(b"Boo")

        runCommand(["git", "add", fragment.path, unrelated.path],
                   cwd=self.repo.path)
        runCommand(["git", "commit", "-m", "topfile"],
                   cwd=self.repo.path)

        logs = []

        with self.assertRaises(SystemExit) as e:
            CheckTopfileScript(logs.append).main([self.repo.path])

        self.assertEqual(e.exception.args, (0,))
        self.assertEqual(logs[-1], "Found twisted/topfiles/1234.misc")
