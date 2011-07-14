# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.release} and L{twisted.python._release}.

All of these tests are skipped on platforms other than Linux, as the release is
only ever performed on Linux.
"""


import warnings
import operator
import os, sys, signal
from StringIO import StringIO
import tarfile
from xml.dom import minidom as dom

from datetime import date

from twisted.trial.unittest import TestCase

from twisted.python.compat import set
from twisted.python.procutils import which
from twisted.python import release
from twisted.python.filepath import FilePath
from twisted.python.versions import Version
from twisted.python._release import _changeVersionInFile, getNextVersion
from twisted.python._release import findTwistedProjects, replaceInFile
from twisted.python._release import replaceProjectVersion
from twisted.python._release import updateTwistedVersionInformation, Project
from twisted.python._release import generateVersionFileData
from twisted.python._release import changeAllProjectVersions
from twisted.python._release import VERSION_OFFSET, DocBuilder, ManBuilder
from twisted.python._release import NoDocumentsFound, filePathDelta
from twisted.python._release import CommandFailed, BookBuilder
from twisted.python._release import DistributionBuilder, APIBuilder
from twisted.python._release import BuildAPIDocsScript
from twisted.python._release import buildAllTarballs, runCommand
from twisted.python._release import UncleanWorkingDirectory, NotWorkingDirectory
from twisted.python._release import ChangeVersionsScript, BuildTarballsScript
from twisted.python._release import NewsBuilder

if os.name != 'posix':
    skip = "Release toolchain only supported on POSIX."
else:
    skip = None


# Check a bunch of dependencies to skip tests if necessary.
try:
    from twisted.lore.scripts import lore
except ImportError:
    loreSkip = "Lore is not present."
else:
    loreSkip = skip


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


if which("latex") and which("dvips") and which("ps2pdf13"):
    latexSkip = skip
else:
    latexSkip = "LaTeX is not available."


if which("svn") and which("svnadmin"):
    svnSkip = skip
else:
    svnSkip = "svn or svnadmin is not present."


def genVersion(*args, **kwargs):
    """
    A convenience for generating _version.py data.

    @param args: Arguments to pass to L{Version}.
    @param kwargs: Keyword arguments to pass to L{Version}.
    """
    return generateVersionFileData(Version(*args, **kwargs))



class StructureAssertingMixin(object):
    """
    A mixin for L{TestCase} subclasses which provides some methods for asserting
    the structure and contents of directories and files on the filesystem.
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
        children = [x.basename() for x in root.children()]
        for x in dirDict:
            child = root.child(x)
            if isinstance(dirDict[x], dict):
                self.assertTrue(child.isdir(), "%s is not a dir!"
                                % (child.path,))
                self.assertStructure(child, dirDict[x])
            else:
                a = child.getContent().replace(os.linesep, '\n')
                self.assertEqual(a, dirDict[x], child.path)
            children.remove(x)
        if children:
            self.fail("There were extra children in %s: %s"
                      % (root.path, children))


    def assertExtractedStructure(self, outputFile, dirDict):
        """
        Assert that a tarfile content is equivalent to one described by a dict.

        @param outputFile: The tar file built by L{DistributionBuilder}.
        @type outputFile: L{FilePath}.
        @param dirDict: The dict that should describe the contents of the
            directory. It should be the same structure as the C{dirDict}
            parameter to L{createStructure}.
        @type dirDict: C{dict}
        """
        tarFile = tarfile.TarFile.open(outputFile.path, "r:bz2")
        extracted = FilePath(self.mktemp())
        extracted.createDirectory()
        for info in tarFile:
            tarFile.extract(info, path=extracted.path)
        self.assertStructure(extracted.children()[0], dirDict)



class ChangeVersionTest(TestCase, StructureAssertingMixin):
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
        directory.makedirs()
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
        self.assertEqual(getNextVersion(version, now=now),
                          Version("twisted", major, 10, 0))


    def test_getNextVersionAfterYearChange(self):
        """
        When calculating the next version to release when a release is
        happening in a later year, the minor version number is reset to 0.
        """
        now = date.today()
        major = now.year - VERSION_OFFSET
        version = Version("twisted", major - 1, 9, 0)
        self.assertEqual(getNextVersion(version, now=now),
                          Version("twisted", major, 0, 0))


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
        L{changeAllProjectVersions} changes all version numbers in _version.py
        and README files for all projects as well as in the the top-level
        README file.
        """
        root = FilePath(self.mktemp())
        root.createDirectory()
        structure = {
            "README": "Hi this is 1.0.0.",
            "twisted": {
                "topfiles": {
                    "README": "Hi this is 1.0.0"},
                "_version.py":
                    genVersion("twisted", 1, 0, 0),
                "web": {
                    "topfiles": {
                        "README": "Hi this is 1.0.0"},
                    "_version.py": genVersion("twisted.web", 1, 0, 0)
                    }}}
        self.createStructure(root, structure)
        changeAllProjectVersions(root, Version("lol", 1, 0, 2))
        outStructure = {
            "README": "Hi this is 1.0.2.",
            "twisted": {
                "topfiles": {
                    "README": "Hi this is 1.0.2"},
                "_version.py":
                    genVersion("twisted", 1, 0, 2),
                "web": {
                    "topfiles": {
                        "README": "Hi this is 1.0.2"},
                    "_version.py": genVersion("twisted.web", 1, 0, 2),
                    }}}
        self.assertStructure(root, outStructure)


    def test_changeAllProjectVersionsPreRelease(self):
        """
        L{changeAllProjectVersions} changes all version numbers in _version.py
        and README files for all projects as well as in the the top-level
        README file. If the old version was a pre-release, it will change the
        version in NEWS files as well.
        """
        root = FilePath(self.mktemp())
        root.createDirectory()
        coreNews = ("Twisted Core 1.0.0 (2009-12-25)\n"
                    "===============================\n"
                    "\n")
        webNews = ("Twisted Web 1.0.0pre1 (2009-12-25)\n"
                   "==================================\n"
                   "\n")
        structure = {
            "README": "Hi this is 1.0.0.",
            "NEWS": coreNews + webNews,
            "twisted": {
                "topfiles": {
                    "README": "Hi this is 1.0.0",
                    "NEWS": coreNews},
                "_version.py":
                    genVersion("twisted", 1, 0, 0),
                "web": {
                    "topfiles": {
                        "README": "Hi this is 1.0.0pre1",
                        "NEWS": webNews},
                    "_version.py": genVersion("twisted.web", 1, 0, 0, 1)
                    }}}
        self.createStructure(root, structure)
        changeAllProjectVersions(root, Version("lol", 1, 0, 2), '2010-01-01')
        coreNews = (
            "Twisted Core 1.0.0 (2009-12-25)\n"
            "===============================\n"
            "\n")
        webNews = ("Twisted Web 1.0.2 (2010-01-01)\n"
                   "==============================\n"
                   "\n")
        outStructure = {
            "README": "Hi this is 1.0.2.",
            "NEWS": coreNews + webNews,
            "twisted": {
                "topfiles": {
                    "README": "Hi this is 1.0.2",
                    "NEWS": coreNews},
                "_version.py":
                    genVersion("twisted", 1, 0, 2),
                "web": {
                    "topfiles": {
                        "README": "Hi this is 1.0.2",
                        "NEWS": webNews},
                    "_version.py": genVersion("twisted.web", 1, 0, 2),
                    }}}
        self.assertStructure(root, outStructure)



class ProjectTest(TestCase):
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
            baseDirectory.createDirectory()
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
        baseDirectory.createDirectory()
        for version in versions:
            self.makeProject(version, baseDirectory)
        return baseDirectory


    def test_getVersion(self):
        """
        Project objects know their version.
        """
        version = Version('foo', 2, 1, 0)
        project = self.makeProject(version)
        self.assertEqual(project.getVersion(), version)


    def test_updateVersion(self):
        """
        Project objects know how to update the version numbers in those
        projects.
        """
        project = self.makeProject(Version("bar", 2, 1, 0))
        newVersion = Version("bar", 3, 2, 9)
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


    def test_updateTwistedVersionInformation(self):
        """
        Update Twisted version information in the top-level project and all of
        the subprojects.
        """
        baseDirectory = FilePath(self.mktemp())
        baseDirectory.createDirectory()
        now = date.today()

        projectName = 'foo'
        oldVersion = Version(projectName, 2, 5, 0)
        newVersion = getNextVersion(oldVersion, now=now)

        project = self.makeProject(oldVersion, baseDirectory)

        updateTwistedVersionInformation(baseDirectory, now=now)

        self.assertEqual(project.getVersion(), newVersion)
        self.assertEqual(
            project.directory.child('topfiles').child('README').getContent(),
            newVersion.base())



class UtilityTest(TestCase):
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
            1/0
        self.assertRaises(ZeroDivisionError,
                          release.runChdirSafe, chAndBreak)
        self.assertEqual(cwd, os.getcwd())



    def test_replaceInFile(self):
        """
        L{replaceInFile} replaces data in a file based on a dict. A key from
        the dict that is found in the file is replaced with the corresponding
        value.
        """
        in_ = 'foo\nhey hey $VER\nbar\n'
        outf = open('release.replace', 'w')
        outf.write(in_)
        outf.close()

        expected = in_.replace('$VER', '2.0.0')
        replaceInFile('release.replace', {'$VER': '2.0.0'})
        self.assertEqual(open('release.replace').read(), expected)


        expected = expected.replace('2.0.0', '3.0.0')
        replaceInFile('release.replace', {'2.0.0': '3.0.0'})
        self.assertEqual(open('release.replace').read(), expected)



class VersionWritingTest(TestCase):
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



class BuilderTestsMixin(object):
    """
    A mixin class which provides various methods for creating sample Lore input
    and output.

    @cvar template: The lore template that will be used to prepare sample
    output.
    @type template: C{str}

    @ivar docCounter: A counter which is incremented every time input is
        generated and which is included in the documents.
    @type docCounter: C{int}
    """
    template = '''
    <html>
    <head><title>Yo:</title></head>
    <body>
    <div class="body" />
    <a href="index.html">Index</a>
    <span class="version">Version: </span>
    </body>
    </html>
    '''

    def setUp(self):
        """
        Initialize the doc counter which ensures documents are unique.
        """
        self.docCounter = 0


    def assertXMLEqual(self, first, second):
        """
        Verify that two strings represent the same XML document.
        """
        self.assertEqual(
            dom.parseString(first).toxml(),
            dom.parseString(second).toxml())


    def getArbitraryOutput(self, version, counter, prefix="", apiBaseURL="%s"):
        """
        Get the correct HTML output for the arbitrary input returned by
        L{getArbitraryLoreInput} for the given parameters.

        @param version: The version string to include in the output.
        @type version: C{str}
        @param counter: A counter to include in the output.
        @type counter: C{int}
        """
        document = """\
<?xml version="1.0"?><html>
    <head><title>Yo:Hi! Title: %(count)d</title></head>
    <body>
    <div class="content">Hi! %(count)d<div class="API"><a href="%(foobarLink)s" title="foobar">foobar</a></div></div>
    <a href="%(prefix)sindex.html">Index</a>
    <span class="version">Version: %(version)s</span>
    </body>
    </html>"""
        # Try to normalize irrelevant whitespace.
        return dom.parseString(
            document % {"count": counter, "prefix": prefix,
                        "version": version,
                        "foobarLink": apiBaseURL % ("foobar",)}).toxml('utf-8')


    def getArbitraryLoreInput(self, counter):
        """
        Get an arbitrary, unique (for this test case) string of lore input.

        @param counter: A counter to include in the input.
        @type counter: C{int}
        """
        template = (
            '<html>'
            '<head><title>Hi! Title: %(count)s</title></head>'
            '<body>'
            'Hi! %(count)s'
            '<div class="API">foobar</div>'
            '</body>'
            '</html>')
        return template % {"count": counter}


    def getArbitraryLoreInputAndOutput(self, version, prefix="",
                                       apiBaseURL="%s"):
        """
        Get an input document along with expected output for lore run on that
        output document, assuming an appropriately-specified C{self.template}.

        @param version: A version string to include in the input and output.
        @type version: C{str}
        @param prefix: The prefix to include in the link to the index.
        @type prefix: C{str}

        @return: A two-tuple of input and expected output.
        @rtype: C{(str, str)}.
        """
        self.docCounter += 1
        return (self.getArbitraryLoreInput(self.docCounter),
                self.getArbitraryOutput(version, self.docCounter,
                                        prefix=prefix, apiBaseURL=apiBaseURL))


    def getArbitraryManInput(self):
        """
        Get an arbitrary man page content.
        """
        return """.TH MANHOLE "1" "August 2001" "" ""
.SH NAME
manhole \- Connect to a Twisted Manhole service
.SH SYNOPSIS
.B manhole
.SH DESCRIPTION
manhole is a GTK interface to Twisted Manhole services. You can execute python
code as if at an interactive Python console inside a running Twisted process
with this."""


    def getArbitraryManLoreOutput(self):
        """
        Get an arbitrary lore input document which represents man-to-lore
        output based on the man page returned from L{getArbitraryManInput}
        """
        return """\
<?xml version="1.0"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html><head>
<title>MANHOLE.1</title></head>
<body>

<h1>MANHOLE.1</h1>

<h2>NAME</h2>

<p>manhole - Connect to a Twisted Manhole service
</p>

<h2>SYNOPSIS</h2>

<p><strong>manhole</strong> </p>

<h2>DESCRIPTION</h2>

<p>manhole is a GTK interface to Twisted Manhole services. You can execute python
code as if at an interactive Python console inside a running Twisted process
with this.</p>

</body>
</html>
"""

    def getArbitraryManHTMLOutput(self, version, prefix=""):
        """
        Get an arbitrary lore output document which represents the lore HTML
        output based on the input document returned from
        L{getArbitraryManLoreOutput}.

        @param version: A version string to include in the document.
        @type version: C{str}
        @param prefix: The prefix to include in the link to the index.
        @type prefix: C{str}
        """
        # Try to normalize the XML a little bit.
        return dom.parseString("""\
<?xml version="1.0" ?><html>
    <head><title>Yo:MANHOLE.1</title></head>
    <body>
    <div class="content">

<span/>

<h2>NAME<a name="auto0"/></h2>

<p>manhole - Connect to a Twisted Manhole service
</p>

<h2>SYNOPSIS<a name="auto1"/></h2>

<p><strong>manhole</strong> </p>

<h2>DESCRIPTION<a name="auto2"/></h2>

<p>manhole is a GTK interface to Twisted Manhole services. You can execute python
code as if at an interactive Python console inside a running Twisted process
with this.</p>

</div>
    <a href="%(prefix)sindex.html">Index</a>
    <span class="version">Version: %(version)s</span>
    </body>
    </html>""" % {
            'prefix': prefix, 'version': version}).toxml("utf-8")



class DocBuilderTestCase(TestCase, BuilderTestsMixin):
    """
    Tests for L{DocBuilder}.

    Note for future maintainers: The exact byte equality assertions throughout
    this suite may need to be updated due to minor differences in lore. They
    should not be taken to mean that Lore must maintain the same byte format
    forever. Feel free to update the tests when Lore changes, but please be
    careful.
    """
    skip = loreSkip

    def setUp(self):
        """
        Set up a few instance variables that will be useful.

        @ivar builder: A plain L{DocBuilder}.
        @ivar docCounter: An integer to be used as a counter by the
            C{getArbitrary...} methods.
        @ivar howtoDir: A L{FilePath} representing a directory to be used for
            containing Lore documents.
        @ivar templateFile: A L{FilePath} representing a file with
            C{self.template} as its content.
        """
        BuilderTestsMixin.setUp(self)
        self.builder = DocBuilder()
        self.howtoDir = FilePath(self.mktemp())
        self.howtoDir.createDirectory()
        self.templateFile = self.howtoDir.child("template.tpl")
        self.templateFile.setContent(self.template)


    def test_build(self):
        """
        The L{DocBuilder} runs lore on all .xhtml files within a directory.
        """
        version = "1.2.3"
        input1, output1 = self.getArbitraryLoreInputAndOutput(version)
        input2, output2 = self.getArbitraryLoreInputAndOutput(version)

        self.howtoDir.child("one.xhtml").setContent(input1)
        self.howtoDir.child("two.xhtml").setContent(input2)

        self.builder.build(version, self.howtoDir, self.howtoDir,
                           self.templateFile)
        out1 = self.howtoDir.child('one.html')
        out2 = self.howtoDir.child('two.html')
        self.assertXMLEqual(out1.getContent(), output1)
        self.assertXMLEqual(out2.getContent(), output2)


    def test_noDocumentsFound(self):
        """
        The C{build} method raises L{NoDocumentsFound} if there are no
        .xhtml files in the given directory.
        """
        self.assertRaises(
            NoDocumentsFound,
            self.builder.build, "1.2.3", self.howtoDir, self.howtoDir,
            self.templateFile)


    def test_parentDocumentLinking(self):
        """
        The L{DocBuilder} generates correct links from documents to
        template-generated links like stylesheets and index backreferences.
        """
        input = self.getArbitraryLoreInput(0)
        tutoDir = self.howtoDir.child("tutorial")
        tutoDir.createDirectory()
        tutoDir.child("child.xhtml").setContent(input)
        self.builder.build("1.2.3", self.howtoDir, tutoDir, self.templateFile)
        outFile = tutoDir.child('child.html')
        self.assertIn('<a href="../index.html">Index</a>',
                      outFile.getContent())


    def test_siblingDirectoryDocumentLinking(self):
        """
        It is necessary to generate documentation in a directory foo/bar where
        stylesheet and indexes are located in foo/baz. Such resources should be
        appropriately linked to.
        """
        input = self.getArbitraryLoreInput(0)
        resourceDir = self.howtoDir.child("resources")
        docDir = self.howtoDir.child("docs")
        docDir.createDirectory()
        docDir.child("child.xhtml").setContent(input)
        self.builder.build("1.2.3", resourceDir, docDir, self.templateFile)
        outFile = docDir.child('child.html')
        self.assertIn('<a href="../resources/index.html">Index</a>',
                      outFile.getContent())


    def test_apiLinking(self):
        """
        The L{DocBuilder} generates correct links from documents to API
        documentation.
        """
        version = "1.2.3"
        input, output = self.getArbitraryLoreInputAndOutput(version)
        self.howtoDir.child("one.xhtml").setContent(input)

        self.builder.build(version, self.howtoDir, self.howtoDir,
                           self.templateFile, "scheme:apilinks/%s.ext")
        out = self.howtoDir.child('one.html')
        self.assertIn(
            '<a href="scheme:apilinks/foobar.ext" title="foobar">foobar</a>',
            out.getContent())


    def test_deleteInput(self):
        """
        L{DocBuilder.build} can be instructed to delete the input files after
        generating the output based on them.
        """
        input1 = self.getArbitraryLoreInput(0)
        self.howtoDir.child("one.xhtml").setContent(input1)
        self.builder.build("whatever", self.howtoDir, self.howtoDir,
                           self.templateFile, deleteInput=True)
        self.assertTrue(self.howtoDir.child('one.html').exists())
        self.assertFalse(self.howtoDir.child('one.xhtml').exists())


    def test_doNotDeleteInput(self):
        """
        Input will not be deleted by default.
        """
        input1 = self.getArbitraryLoreInput(0)
        self.howtoDir.child("one.xhtml").setContent(input1)
        self.builder.build("whatever", self.howtoDir, self.howtoDir,
                           self.templateFile)
        self.assertTrue(self.howtoDir.child('one.html').exists())
        self.assertTrue(self.howtoDir.child('one.xhtml').exists())


    def test_getLinkrelToSameDirectory(self):
        """
        If the doc and resource directories are the same, the linkrel should be
        an empty string.
        """
        linkrel = self.builder.getLinkrel(FilePath("/foo/bar"),
                                          FilePath("/foo/bar"))
        self.assertEqual(linkrel, "")


    def test_getLinkrelToParentDirectory(self):
        """
        If the doc directory is a child of the resource directory, the linkrel
        should make use of '..'.
        """
        linkrel = self.builder.getLinkrel(FilePath("/foo"),
                                          FilePath("/foo/bar"))
        self.assertEqual(linkrel, "../")


    def test_getLinkrelToSibling(self):
        """
        If the doc directory is a sibling of the resource directory, the
        linkrel should make use of '..' and a named segment.
        """
        linkrel = self.builder.getLinkrel(FilePath("/foo/howto"),
                                          FilePath("/foo/examples"))
        self.assertEqual(linkrel, "../howto/")


    def test_getLinkrelToUncle(self):
        """
        If the doc directory is a sibling of the parent of the resource
        directory, the linkrel should make use of multiple '..'s and a named
        segment.
        """
        linkrel = self.builder.getLinkrel(FilePath("/foo/howto"),
                                          FilePath("/foo/examples/quotes"))
        self.assertEqual(linkrel, "../../howto/")



class APIBuilderTestCase(TestCase):
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
        outputPath.makedirs()

        builder = APIBuilder()
        builder.build(projectName, projectURL, sourceURL, inputPath, outputPath)

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
            '<a href="%s/%s/__init__.py#L1" class="functionSourceLink">' % (
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
            '<a href="http://twistedmatrix.com/trac/browser/tags/releases/'
            'twisted-1.0.0/twisted">View Source</a>',
            twistedPath.getContent())

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



class ManBuilderTestCase(TestCase, BuilderTestsMixin):
    """
    Tests for L{ManBuilder}.
    """
    skip = loreSkip

    def setUp(self):
        """
        Set up a few instance variables that will be useful.

        @ivar builder: A plain L{ManBuilder}.
        @ivar manDir: A L{FilePath} representing a directory to be used for
            containing man pages.
        """
        BuilderTestsMixin.setUp(self)
        self.builder = ManBuilder()
        self.manDir = FilePath(self.mktemp())
        self.manDir.createDirectory()


    def test_noDocumentsFound(self):
        """
        L{ManBuilder.build} raises L{NoDocumentsFound} if there are no
        .1 files in the given directory.
        """
        self.assertRaises(NoDocumentsFound, self.builder.build, self.manDir)


    def test_build(self):
        """
        Check that L{ManBuilder.build} find the man page in the directory, and
        successfully produce a Lore content.
        """
        manContent = self.getArbitraryManInput()
        self.manDir.child('test1.1').setContent(manContent)
        self.builder.build(self.manDir)
        output = self.manDir.child('test1-man.xhtml').getContent()
        expected = self.getArbitraryManLoreOutput()
        # No-op on *nix, fix for windows
        expected = expected.replace('\n', os.linesep)
        self.assertEqual(output, expected)


    def test_toHTML(self):
        """
        Check that the content output by C{build} is compatible as input of
        L{DocBuilder.build}.
        """
        manContent = self.getArbitraryManInput()
        self.manDir.child('test1.1').setContent(manContent)
        self.builder.build(self.manDir)

        templateFile = self.manDir.child("template.tpl")
        templateFile.setContent(DocBuilderTestCase.template)
        docBuilder = DocBuilder()
        docBuilder.build("1.2.3", self.manDir, self.manDir,
                         templateFile)
        output = self.manDir.child('test1-man.html').getContent()

        self.assertXMLEqual(
            output,
            """\
<?xml version="1.0" ?><html>
    <head><title>Yo:MANHOLE.1</title></head>
    <body>
    <div class="content">

<span/>

<h2>NAME<a name="auto0"/></h2>

<p>manhole - Connect to a Twisted Manhole service
</p>

<h2>SYNOPSIS<a name="auto1"/></h2>

<p><strong>manhole</strong> </p>

<h2>DESCRIPTION<a name="auto2"/></h2>

<p>manhole is a GTK interface to Twisted Manhole services. You can execute python
code as if at an interactive Python console inside a running Twisted process
with this.</p>

</div>
    <a href="index.html">Index</a>
    <span class="version">Version: 1.2.3</span>
    </body>
    </html>""")



class BookBuilderTests(TestCase, BuilderTestsMixin):
    """
    Tests for L{BookBuilder}.
    """
    skip = latexSkip or loreSkip

    def setUp(self):
        """
        Make a directory into which to place temporary files.
        """
        self.docCounter = 0
        self.howtoDir = FilePath(self.mktemp())
        self.howtoDir.makedirs()
        self.oldHandler = signal.signal(signal.SIGCHLD, signal.SIG_DFL)


    def tearDown(self):
        signal.signal(signal.SIGCHLD, self.oldHandler)


    def getArbitraryOutput(self, version, counter, prefix="", apiBaseURL=None):
        """
        Create and return a C{str} containing the LaTeX document which is
        expected as the output for processing the result of the document
        returned by C{self.getArbitraryLoreInput(counter)}.
        """
        path = self.howtoDir.child("%d.xhtml" % (counter,)).path
        return (
            r'\section{Hi! Title: %(count)s\label{%(path)s}}'
            '\n'
            r'Hi! %(count)sfoobar') % {'count': counter, 'path': path}


    def test_runSuccess(self):
        """
        L{BookBuilder.run} executes the command it is passed and returns a
        string giving the stdout and stderr of the command if it completes
        successfully.
        """
        builder = BookBuilder()
        self.assertEqual(
                builder.run([
                    sys.executable, '-c',
                    'import sys; '
                    'sys.stdout.write("hi\\n"); '
                    'sys.stdout.flush(); '
                    'sys.stderr.write("bye\\n"); '
                    'sys.stderr.flush()']),
                "hi\nbye\n")


    def test_runFailed(self):
        """
        L{BookBuilder.run} executes the command it is passed and raises
        L{CommandFailed} if it completes unsuccessfully.
        """
        builder = BookBuilder()
        exc = self.assertRaises(
            CommandFailed, builder.run,
            [sys.executable, '-c', 'print "hi"; raise SystemExit(1)'])
        self.assertEqual(exc.exitStatus, 1)
        self.assertEqual(exc.exitSignal, None)
        self.assertEqual(exc.output, "hi\n")


    def test_runSignaled(self):
        """
        L{BookBuilder.run} executes the command it is passed and raises
        L{CommandFailed} if it exits due to a signal.
        """
        builder = BookBuilder()
        exc = self.assertRaises(
            CommandFailed, builder.run,
            [sys.executable, '-c',
            'import sys; print "hi"; sys.stdout.flush(); '
            'import os; os.kill(os.getpid(), 9)'])
        self.assertEqual(exc.exitSignal, 9)
        self.assertEqual(exc.exitStatus, None)
        self.assertEqual(exc.output, "hi\n")


    def test_buildTeX(self):
        """
        L{BookBuilder.buildTeX} writes intermediate TeX files for all lore
        input files in a directory.
        """
        version = "3.2.1"
        input1, output1 = self.getArbitraryLoreInputAndOutput(version)
        input2, output2 = self.getArbitraryLoreInputAndOutput(version)

        # Filenames are chosen by getArbitraryOutput to match the counter used
        # by getArbitraryLoreInputAndOutput.
        self.howtoDir.child("1.xhtml").setContent(input1)
        self.howtoDir.child("2.xhtml").setContent(input2)

        builder = BookBuilder()
        builder.buildTeX(self.howtoDir)
        self.assertEqual(self.howtoDir.child("1.tex").getContent(), output1)
        self.assertEqual(self.howtoDir.child("2.tex").getContent(), output2)


    def test_buildTeXRejectsInvalidDirectory(self):
        """
        L{BookBuilder.buildTeX} raises L{ValueError} if passed a directory
        which does not exist.
        """
        builder = BookBuilder()
        self.assertRaises(
            ValueError, builder.buildTeX, self.howtoDir.temporarySibling())


    def test_buildTeXOnlyBuildsXHTML(self):
        """
        L{BookBuilder.buildTeX} ignores files which which don't end with
        ".xhtml".
        """
        # Hopefully ">" is always a parse error from microdom!
        self.howtoDir.child("not-input.dat").setContent(">")
        self.test_buildTeX()


    def test_stdout(self):
        """
        L{BookBuilder.buildTeX} does not write to stdout.
        """
        stdout = StringIO()
        self.patch(sys, 'stdout', stdout)

        # Suppress warnings so that if there are any old-style plugins that
        # lore queries for don't confuse the assertion below.  See #3070.
        self.patch(warnings, 'warn', lambda *a, **kw: None)
        self.test_buildTeX()
        self.assertEqual(stdout.getvalue(), '')


    def test_buildPDFRejectsInvalidBookFilename(self):
        """
        L{BookBuilder.buildPDF} raises L{ValueError} if the book filename does
        not end with ".tex".
        """
        builder = BookBuilder()
        self.assertRaises(
            ValueError,
            builder.buildPDF,
            FilePath(self.mktemp()).child("foo"),
            None,
            None)


    def _setupTeXFiles(self):
        sections = range(3)
        self._setupTeXSections(sections)
        return self._setupTeXBook(sections)


    def _setupTeXSections(self, sections):
        for texSectionNumber in sections:
            texPath = self.howtoDir.child("%d.tex" % (texSectionNumber,))
            texPath.setContent(self.getArbitraryOutput(
                    "1.2.3", texSectionNumber))


    def _setupTeXBook(self, sections):
        bookTeX = self.howtoDir.child("book.tex")
        bookTeX.setContent(
            r"\documentclass{book}" "\n"
            r"\begin{document}" "\n" +
            "\n".join([r"\input{%d.tex}" % (n,) for n in sections]) +
            r"\end{document}" "\n")
        return bookTeX


    def test_buildPDF(self):
        """
        L{BookBuilder.buildPDF} creates a PDF given an index tex file and a
        directory containing .tex files.
        """
        bookPath = self._setupTeXFiles()
        outputPath = FilePath(self.mktemp())

        builder = BookBuilder()
        builder.buildPDF(bookPath, self.howtoDir, outputPath)

        self.assertTrue(outputPath.exists())


    def test_buildPDFLongPath(self):
        """
        L{BookBuilder.buildPDF} succeeds even if the paths it is operating on
        are very long.

        C{ps2pdf13} seems to have problems when path names are long.  This test
        verifies that even if inputs have long paths, generation still
        succeeds.
        """
        # Make it long.
        self.howtoDir = self.howtoDir.child("x" * 128).child("x" * 128).child("x" * 128)
        self.howtoDir.makedirs()

        # This will use the above long path.
        bookPath = self._setupTeXFiles()
        outputPath = FilePath(self.mktemp())

        builder = BookBuilder()
        builder.buildPDF(bookPath, self.howtoDir, outputPath)

        self.assertTrue(outputPath.exists())


    def test_buildPDFRunsLaTeXThreeTimes(self):
        """
        L{BookBuilder.buildPDF} runs C{latex} three times.
        """
        class InspectableBookBuilder(BookBuilder):
            def __init__(self):
                BookBuilder.__init__(self)
                self.commands = []

            def run(self, command):
                """
                Record the command and then execute it.
                """
                self.commands.append(command)
                return BookBuilder.run(self, command)

        bookPath = self._setupTeXFiles()
        outputPath = FilePath(self.mktemp())

        builder = InspectableBookBuilder()
        builder.buildPDF(bookPath, self.howtoDir, outputPath)

        # These string comparisons are very fragile.  It would be better to
        # have a test which asserted the correctness of the contents of the
        # output files.  I don't know how one could do that, though. -exarkun
        latex1, latex2, latex3, dvips, ps2pdf13 = builder.commands
        self.assertEqual(latex1, latex2)
        self.assertEqual(latex2, latex3)
        self.assertEqual(
            latex1[:1], ["latex"],
            "LaTeX command %r does not seem right." % (latex1,))
        self.assertEqual(
            latex1[-1:], [bookPath.path],
            "LaTeX command %r does not end with the book path (%r)." % (
                latex1, bookPath.path))

        self.assertEqual(
            dvips[:1], ["dvips"],
            "dvips command %r does not seem right." % (dvips,))
        self.assertEqual(
            ps2pdf13[:1], ["ps2pdf13"],
            "ps2pdf13 command %r does not seem right." % (ps2pdf13,))


    def test_noSideEffects(self):
        """
        The working directory is the same before and after a call to
        L{BookBuilder.buildPDF}.  Also the contents of the directory containing
        the input book are the same before and after the call.
        """
        startDir = os.getcwd()
        bookTeX = self._setupTeXFiles()
        startTeXSiblings = bookTeX.parent().children()
        startHowtoChildren = self.howtoDir.children()

        builder = BookBuilder()
        builder.buildPDF(bookTeX, self.howtoDir, FilePath(self.mktemp()))

        self.assertEqual(startDir, os.getcwd())
        self.assertEqual(startTeXSiblings, bookTeX.parent().children())
        self.assertEqual(startHowtoChildren, self.howtoDir.children())


    def test_failedCommandProvidesOutput(self):
        """
        If a subprocess fails, L{BookBuilder.buildPDF} raises L{CommandFailed}
        with the subprocess's output and leaves the temporary directory as a
        sibling of the book path.
        """
        bookTeX = FilePath(self.mktemp() + ".tex")
        builder = BookBuilder()
        inputState = bookTeX.parent().children()
        exc = self.assertRaises(
            CommandFailed,
            builder.buildPDF,
            bookTeX, self.howtoDir, FilePath(self.mktemp()))
        self.assertTrue(exc.output)
        newOutputState = set(bookTeX.parent().children()) - set(inputState)
        self.assertEqual(len(newOutputState), 1)
        workPath = newOutputState.pop()
        self.assertTrue(
            workPath.isdir(),
            "Expected work path %r was not a directory." % (workPath.path,))


    def test_build(self):
        """
        L{BookBuilder.build} generates a pdf book file from some lore input
        files.
        """
        sections = range(1, 4)
        for sectionNumber in sections:
            self.howtoDir.child("%d.xhtml" % (sectionNumber,)).setContent(
                self.getArbitraryLoreInput(sectionNumber))
        bookTeX = self._setupTeXBook(sections)
        bookPDF = FilePath(self.mktemp())

        builder = BookBuilder()
        builder.build(self.howtoDir, [self.howtoDir], bookTeX, bookPDF)

        self.assertTrue(bookPDF.exists())


    def test_buildRemovesTemporaryLaTeXFiles(self):
        """
        L{BookBuilder.build} removes the intermediate LaTeX files it creates.
        """
        sections = range(1, 4)
        for sectionNumber in sections:
            self.howtoDir.child("%d.xhtml" % (sectionNumber,)).setContent(
                self.getArbitraryLoreInput(sectionNumber))
        bookTeX = self._setupTeXBook(sections)
        bookPDF = FilePath(self.mktemp())

        builder = BookBuilder()
        builder.build(self.howtoDir, [self.howtoDir], bookTeX, bookPDF)

        self.assertEqual(
            set(self.howtoDir.listdir()),
            set([bookTeX.basename()] + ["%d.xhtml" % (n,) for n in sections]))



class FilePathDeltaTest(TestCase):
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



class NewsBuilderTests(TestCase, StructureAssertingMixin):
    """
    Tests for L{NewsBuilder}.
    """
    def setUp(self):
        """
        Create a fake project and stuff some basic structure and content into
        it.
        """
        self.builder = NewsBuilder()
        self.project = FilePath(self.mktemp())
        self.project.createDirectory()
        self.existingText = 'Here is stuff which was present previously.\n'
        self.createStructure(self.project, {
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
            " - Very long line which goes on and on and on, seemingly without end\n"
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
            " - #2, #5, #8, #11, #14, #17, #20, #23, #26, #29, #32, #35, #38, #41,\n"
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
            ' - A very long feature which takes many words to describe with any\n'
            '   accuracy was introduced so that the line wrapping behavior of the\n'
            '   news generating code could be verified. (#15)\n'
            ' - A simpler feature described on multiple lines was added. (#16)\n'
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
        self.createStructure(project, {
                'NEWS': self.existingText })

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
            ' - A very long feature which takes many words to describe with any\n'
            '   accuracy was introduced so that the line wrapping behavior of the\n'
            '   news generating code could be verified. (#15)\n'
            ' - A simpler feature described on multiple lines was added. (#16)\n'
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
        self.createStructure(project, {
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
                        '7.bugfix': 'Fixed that bug.\n'}},
                })
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

        project = self.createFakeTwistedProject()
        builder.buildAll(project)

        coreTopfiles = project.child("topfiles")
        coreNews = coreTopfiles.child("NEWS")
        coreHeader = "Twisted Core 1.2.3 (2009-12-01)"

        conchTopfiles = project.child("conch").child("topfiles")
        conchNews = conchTopfiles.child("NEWS")
        conchHeader = "Twisted Conch 3.4.5 (2009-12-01)"

        aggregateNews = project.child("NEWS")

        self.assertEqual(
            builds,
            [(conchTopfiles, conchNews, conchHeader),
             (coreTopfiles, coreNews, coreHeader),
             (conchTopfiles, aggregateNews, conchHeader),
             (coreTopfiles, aggregateNews, coreHeader)])


    def test_changeVersionInNews(self):
        """
        L{NewsBuilder._changeVersions} gets the release date for a given
        version of a project as a string.
        """
        builder = NewsBuilder()
        builder._today = lambda: '2009-12-01'
        project = self.createFakeTwistedProject()
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



class DistributionBuilderTestBase(BuilderTestsMixin, StructureAssertingMixin,
                                   TestCase):
    """
    Base for tests of L{DistributionBuilder}.
    """
    skip = loreSkip

    def setUp(self):
        BuilderTestsMixin.setUp(self)

        self.rootDir = FilePath(self.mktemp())
        self.rootDir.createDirectory()

        self.outputDir = FilePath(self.mktemp())
        self.outputDir.createDirectory()
        self.builder = DistributionBuilder(self.rootDir, self.outputDir)



class DistributionBuilderTest(DistributionBuilderTestBase):

    def test_twistedDistribution(self):
        """
        The Twisted tarball contains everything in the source checkout, with
        built documentation.
        """
        loreInput, loreOutput = self.getArbitraryLoreInputAndOutput("10.0.0")
        manInput1 = self.getArbitraryManInput()
        manOutput1 = self.getArbitraryManHTMLOutput("10.0.0", "../howto/")
        manInput2 = self.getArbitraryManInput()
        manOutput2 = self.getArbitraryManHTMLOutput("10.0.0", "../howto/")
        coreIndexInput, coreIndexOutput = self.getArbitraryLoreInputAndOutput(
            "10.0.0", prefix="howto/")

        structure = {
            "README": "Twisted",
            "unrelated": "x",
            "LICENSE": "copyright!",
            "setup.py": "import toplevel",
            "bin": {"web": {"websetroot": "SET ROOT"},
                    "twistd": "TWISTD"},
            "twisted":
                {"web":
                     {"__init__.py": "import WEB",
                      "topfiles": {"setup.py": "import WEBINSTALL",
                                   "README": "WEB!"}},
                 "words": {"__init__.py": "import WORDS"},
                 "plugins": {"twisted_web.py": "import WEBPLUG",
                             "twisted_words.py": "import WORDPLUG"}},
            "doc": {"web": {"howto": {"index.xhtml": loreInput},
                            "man": {"websetroot.1": manInput2}},
                    "core": {"howto": {"template.tpl": self.template},
                             "man": {"twistd.1": manInput1},
                             "index.xhtml": coreIndexInput}}}

        outStructure = {
            "README": "Twisted",
            "unrelated": "x",
            "LICENSE": "copyright!",
            "setup.py": "import toplevel",
            "bin": {"web": {"websetroot": "SET ROOT"},
                    "twistd": "TWISTD"},
            "twisted":
                {"web": {"__init__.py": "import WEB",
                         "topfiles": {"setup.py": "import WEBINSTALL",
                                      "README": "WEB!"}},
                 "words": {"__init__.py": "import WORDS"},
                 "plugins": {"twisted_web.py": "import WEBPLUG",
                             "twisted_words.py": "import WORDPLUG"}},
            "doc": {"web": {"howto": {"index.html": loreOutput},
                            "man": {"websetroot.1": manInput2,
                                    "websetroot-man.html": manOutput2}},
                    "core": {"howto": {"template.tpl": self.template},
                             "man": {"twistd.1": manInput1,
                                     "twistd-man.html": manOutput1},
                             "index.html": coreIndexOutput}}}

        self.createStructure(self.rootDir, structure)

        outputFile = self.builder.buildTwisted("10.0.0")

        self.assertExtractedStructure(outputFile, outStructure)


    def test_subProjectLayout(self):
        """
        The subproject tarball includes files like so:

        1. twisted/<subproject>/topfiles defines the files that will be in the
           top level in the tarball, except LICENSE, which comes from the real
           top-level directory.
        2. twisted/<subproject> is included, but without the topfiles entry
           in that directory. No other twisted subpackages are included.
        3. twisted/plugins/twisted_<subproject>.py is included, but nothing
           else in plugins is.
        """
        structure = {
            "README": "HI!@",
            "unrelated": "x",
            "LICENSE": "copyright!",
            "setup.py": "import toplevel",
            "bin": {"web": {"websetroot": "SET ROOT"},
                    "words": {"im": "#!im"}},
            "twisted":
                {"web":
                     {"__init__.py": "import WEB",
                      "topfiles": {"setup.py": "import WEBINSTALL",
                                   "README": "WEB!"}},
                 "words": {"__init__.py": "import WORDS"},
                 "plugins": {"twisted_web.py": "import WEBPLUG",
                             "twisted_words.py": "import WORDPLUG"}}}

        outStructure = {
            "README": "WEB!",
            "LICENSE": "copyright!",
            "setup.py": "import WEBINSTALL",
            "bin": {"websetroot": "SET ROOT"},
            "twisted": {"web": {"__init__.py": "import WEB"},
                        "plugins": {"twisted_web.py": "import WEBPLUG"}}}

        self.createStructure(self.rootDir, structure)

        outputFile = self.builder.buildSubProject("web", "0.3.0")

        self.assertExtractedStructure(outputFile, outStructure)


    def test_minimalSubProjectLayout(self):
        """
        buildSubProject should work with minimal subprojects.
        """
        structure = {
            "LICENSE": "copyright!",
            "bin": {},
            "twisted":
                {"web": {"__init__.py": "import WEB",
                         "topfiles": {"setup.py": "import WEBINSTALL"}},
                 "plugins": {}}}

        outStructure = {
            "setup.py": "import WEBINSTALL",
            "LICENSE": "copyright!",
            "twisted": {"web": {"__init__.py": "import WEB"}}}

        self.createStructure(self.rootDir, structure)

        outputFile = self.builder.buildSubProject("web", "0.3.0")

        self.assertExtractedStructure(outputFile, outStructure)


    def test_subProjectDocBuilding(self):
        """
        When building a subproject release, documentation should be built with
        lore.
        """
        loreInput, loreOutput = self.getArbitraryLoreInputAndOutput("0.3.0")
        manInput = self.getArbitraryManInput()
        manOutput = self.getArbitraryManHTMLOutput("0.3.0", "../howto/")
        structure = {
            "LICENSE": "copyright!",
            "twisted": {"web": {"__init__.py": "import WEB",
                                "topfiles": {"setup.py": "import WEBINST"}}},
            "doc": {"web": {"howto": {"index.xhtml": loreInput},
                            "man": {"twistd.1": manInput}},
                    "core": {"howto": {"template.tpl": self.template}}
                    }
            }

        outStructure = {
            "LICENSE": "copyright!",
            "setup.py": "import WEBINST",
            "twisted": {"web": {"__init__.py": "import WEB"}},
            "doc": {"howto": {"index.html": loreOutput},
                    "man": {"twistd.1": manInput,
                            "twistd-man.html": manOutput}}}

        self.createStructure(self.rootDir, structure)

        outputFile = self.builder.buildSubProject("web", "0.3.0")

        self.assertExtractedStructure(outputFile, outStructure)


    def test_coreProjectLayout(self):
        """
        The core tarball looks a lot like a subproject tarball, except it
        doesn't include:

        - Python packages from other subprojects
        - plugins from other subprojects
        - scripts from other subprojects
        """
        indexInput, indexOutput = self.getArbitraryLoreInputAndOutput(
            "8.0.0", prefix="howto/")
        howtoInput, howtoOutput = self.getArbitraryLoreInputAndOutput("8.0.0")
        specInput, specOutput = self.getArbitraryLoreInputAndOutput(
            "8.0.0", prefix="../howto/")
        upgradeInput, upgradeOutput = self.getArbitraryLoreInputAndOutput(
            "8.0.0", prefix="../howto/")
        tutorialInput, tutorialOutput = self.getArbitraryLoreInputAndOutput(
            "8.0.0", prefix="../")

        structure = {
            "LICENSE": "copyright!",
            "twisted": {"__init__.py": "twisted",
                        "python": {"__init__.py": "python",
                                   "roots.py": "roots!"},
                        "conch": {"__init__.py": "conch",
                                  "unrelated.py": "import conch"},
                        "plugin.py": "plugin",
                        "plugins": {"twisted_web.py": "webplug",
                                    "twisted_whatever.py": "include!",
                                    "cred.py": "include!"},
                        "topfiles": {"setup.py": "import CORE",
                                     "README": "core readme"}},
            "doc": {"core": {"howto": {"template.tpl": self.template,
                                       "index.xhtml": howtoInput,
                                       "tutorial":
                                           {"index.xhtml": tutorialInput}},
                             "specifications": {"index.xhtml": specInput},
                             "upgrades": {"index.xhtml": upgradeInput},
                             "examples": {"foo.py": "foo.py"},
                             "index.xhtml": indexInput},
                    "web": {"howto": {"index.xhtml": "webindex"}}},
            "bin": {"twistd": "TWISTD",
                    "web": {"websetroot": "websetroot"}}
            }

        outStructure = {
            "LICENSE": "copyright!",
            "setup.py": "import CORE",
            "README": "core readme",
            "twisted": {"__init__.py": "twisted",
                        "python": {"__init__.py": "python",
                                   "roots.py": "roots!"},
                        "plugin.py": "plugin",
                        "plugins": {"twisted_whatever.py": "include!",
                                    "cred.py": "include!"}},
            "doc": {"howto": {"template.tpl": self.template,
                              "index.html": howtoOutput,
                              "tutorial": {"index.html": tutorialOutput}},
                    "specifications": {"index.html": specOutput},
                    "upgrades": {"index.html": upgradeOutput},
                    "examples": {"foo.py": "foo.py"},
                    "index.html": indexOutput},
            "bin": {"twistd": "TWISTD"},
            }

        self.createStructure(self.rootDir, structure)
        outputFile = self.builder.buildCore("8.0.0")
        self.assertExtractedStructure(outputFile, outStructure)


    def test_apiBaseURL(self):
        """
        DistributionBuilder builds documentation with the specified
        API base URL.
        """
        apiBaseURL = "http://%s"
        builder = DistributionBuilder(self.rootDir, self.outputDir,
                                      apiBaseURL=apiBaseURL)
        loreInput, loreOutput = self.getArbitraryLoreInputAndOutput(
            "0.3.0", apiBaseURL=apiBaseURL)
        structure = {
            "LICENSE": "copyright!",
            "twisted": {"web": {"__init__.py": "import WEB",
                                "topfiles": {"setup.py": "import WEBINST"}}},
            "doc": {"web": {"howto": {"index.xhtml": loreInput}},
                    "core": {"howto": {"template.tpl": self.template}}
                    }
            }

        outStructure = {
            "LICENSE": "copyright!",
            "setup.py": "import WEBINST",
            "twisted": {"web": {"__init__.py": "import WEB"}},
            "doc": {"howto": {"index.html": loreOutput}}}

        self.createStructure(self.rootDir, structure)
        outputFile = builder.buildSubProject("web", "0.3.0")
        self.assertExtractedStructure(outputFile, outStructure)



class BuildAllTarballsTest(DistributionBuilderTestBase):
    """
    Tests for L{DistributionBuilder.buildAllTarballs}.
    """
    skip = svnSkip

    def setUp(self):
        self.oldHandler = signal.signal(signal.SIGCHLD, signal.SIG_DFL)
        DistributionBuilderTestBase.setUp(self)


    def tearDown(self):
        signal.signal(signal.SIGCHLD, self.oldHandler)
        DistributionBuilderTestBase.tearDown(self)


    def test_buildAllTarballs(self):
        """
        L{buildAllTarballs} builds tarballs for Twisted and all of its
        subprojects based on an SVN checkout; the resulting tarballs contain
        no SVN metadata.  This involves building documentation, which it will
        build with the correct API documentation reference base URL.
        """
        repositoryPath = self.mktemp()
        repository = FilePath(repositoryPath)
        checkoutPath = self.mktemp()
        checkout = FilePath(checkoutPath)
        self.outputDir.remove()

        runCommand(["svnadmin", "create", repositoryPath])
        runCommand(["svn", "checkout", "file://" + repository.path,
                    checkout.path])
        coreIndexInput, coreIndexOutput = self.getArbitraryLoreInputAndOutput(
            "1.2.0", prefix="howto/",
            apiBaseURL="http://twistedmatrix.com/documents/1.2.0/api/%s.html")

        structure = {
            "README": "Twisted",
            "unrelated": "x",
            "LICENSE": "copyright!",
            "setup.py": "import toplevel",
            "bin": {"words": {"im": "import im"},
                    "twistd": "TWISTD"},
            "twisted":
                {
                    "topfiles": {"setup.py": "import TOPINSTALL",
                                 "README": "CORE!"},
                    "_version.py": genVersion("twisted", 1, 2, 0),
                    "words": {"__init__.py": "import WORDS",
                              "_version.py":
                                  genVersion("twisted.words", 1, 2, 0),
                              "topfiles": {"setup.py": "import WORDSINSTALL",
                                           "README": "WORDS!"},
                              },
                    "plugins": {"twisted_web.py": "import WEBPLUG",
                                "twisted_words.py": "import WORDPLUG",
                                "twisted_yay.py": "import YAY"}},
            "doc": {"core": {"howto": {"template.tpl": self.template},
                             "index.xhtml": coreIndexInput}}}

        twistedStructure = {
            "README": "Twisted",
            "unrelated": "x",
            "LICENSE": "copyright!",
            "setup.py": "import toplevel",
            "bin": {"twistd": "TWISTD",
                    "words": {"im": "import im"}},
            "twisted":
                {
                    "topfiles": {"setup.py": "import TOPINSTALL",
                                 "README": "CORE!"},
                    "_version.py": genVersion("twisted", 1, 2, 0),
                    "words": {"__init__.py": "import WORDS",
                              "_version.py":
                                  genVersion("twisted.words", 1, 2, 0),
                              "topfiles": {"setup.py": "import WORDSINSTALL",
                                           "README": "WORDS!"},
                              },
                    "plugins": {"twisted_web.py": "import WEBPLUG",
                                "twisted_words.py": "import WORDPLUG",
                                "twisted_yay.py": "import YAY"}},
            "doc": {"core": {"howto": {"template.tpl": self.template},
                             "index.html": coreIndexOutput}}}

        coreStructure = {
            "setup.py": "import TOPINSTALL",
            "README": "CORE!",
            "LICENSE": "copyright!",
            "bin": {"twistd": "TWISTD"},
            "twisted": {
                "_version.py": genVersion("twisted", 1, 2, 0),
                "plugins": {"twisted_yay.py": "import YAY"}},
            "doc": {"howto": {"template.tpl": self.template},
                    "index.html": coreIndexOutput}}

        wordsStructure = {
            "README": "WORDS!",
            "LICENSE": "copyright!",
            "setup.py": "import WORDSINSTALL",
            "bin": {"im": "import im"},
            "twisted":
                {
                    "words": {"__init__.py": "import WORDS",
                              "_version.py":
                                  genVersion("twisted.words", 1, 2, 0),
                              },
                    "plugins": {"twisted_words.py": "import WORDPLUG"}}}

        self.createStructure(checkout, structure)
        childs = [x.path for x in checkout.children()]
        runCommand(["svn", "add"] + childs)
        runCommand(["svn", "commit", checkout.path, "-m", "yay"])

        buildAllTarballs(checkout, self.outputDir)
        self.assertEqual(
            set(self.outputDir.children()),
            set([self.outputDir.child("Twisted-1.2.0.tar.bz2"),
                 self.outputDir.child("TwistedCore-1.2.0.tar.bz2"),
                 self.outputDir.child("TwistedWords-1.2.0.tar.bz2")]))

        self.assertExtractedStructure(
            self.outputDir.child("Twisted-1.2.0.tar.bz2"),
            twistedStructure)
        self.assertExtractedStructure(
            self.outputDir.child("TwistedCore-1.2.0.tar.bz2"),
            coreStructure)
        self.assertExtractedStructure(
            self.outputDir.child("TwistedWords-1.2.0.tar.bz2"),
            wordsStructure)


    def test_buildAllTarballsEnsuresCleanCheckout(self):
        """
        L{UncleanWorkingDirectory} is raised by L{buildAllTarballs} when the
        SVN checkout provided has uncommitted changes.
        """
        repositoryPath = self.mktemp()
        repository = FilePath(repositoryPath)
        checkoutPath = self.mktemp()
        checkout = FilePath(checkoutPath)

        runCommand(["svnadmin", "create", repositoryPath])
        runCommand(["svn", "checkout", "file://" + repository.path,
                    checkout.path])

        checkout.child("foo").setContent("whatever")
        self.assertRaises(UncleanWorkingDirectory,
                          buildAllTarballs, checkout, FilePath(self.mktemp()))


    def test_buildAllTarballsEnsuresExistingCheckout(self):
        """
        L{NotWorkingDirectory} is raised by L{buildAllTarballs} when the
        checkout passed does not exist or is not an SVN checkout.
        """
        checkout = FilePath(self.mktemp())
        self.assertRaises(NotWorkingDirectory,
                          buildAllTarballs,
                          checkout, FilePath(self.mktemp()))
        checkout.createDirectory()
        self.assertRaises(NotWorkingDirectory,
                          buildAllTarballs,
                          checkout, FilePath(self.mktemp()))



class ScriptTests(BuilderTestsMixin, StructureAssertingMixin, TestCase):
    """
    Tests for the release script functionality.
    """

    def _testVersionChanging(self, major, minor, micro, prerelease=None):
        """
        Check that L{ChangeVersionsScript.main} calls the version-changing
        function with the appropriate version data and filesystem path.
        """
        versionUpdates = []
        def myVersionChanger(sourceTree, versionTemplate):
            versionUpdates.append((sourceTree, versionTemplate))
        versionChanger = ChangeVersionsScript()
        versionChanger.changeAllProjectVersions = myVersionChanger
        version = "%d.%d.%d" % (major, minor, micro)
        if prerelease is not None:
            version += "pre%d" % (prerelease,)
        versionChanger.main([version])
        self.assertEqual(len(versionUpdates), 1)
        self.assertEqual(versionUpdates[0][0], FilePath("."))
        self.assertEqual(versionUpdates[0][1].major, major)
        self.assertEqual(versionUpdates[0][1].minor, minor)
        self.assertEqual(versionUpdates[0][1].micro, micro)
        self.assertEqual(versionUpdates[0][1].prerelease, prerelease)


    def test_changeVersions(self):
        """
        L{ChangeVersionsScript.main} changes version numbers for all Twisted
        projects.
        """
        self._testVersionChanging(8, 2, 3)


    def test_changeVersionsWithPrerelease(self):
        """
        A prerelease can be specified to L{changeVersionsScript}.
        """
        self._testVersionChanging(9, 2, 7, 38)


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
        L{changeVersionsScript} raises SystemExit when the wrong number of
        arguments are passed.
        """
        versionChanger = ChangeVersionsScript()
        self.assertRaises(SystemExit, versionChanger.main, [])


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


    def test_buildTarballsScript(self):
        """
        L{BuildTarballsScript.main} invokes L{buildAllTarballs} with
        L{FilePath} instances representing the paths passed to it.
        """
        builds = []
        def myBuilder(checkout, destination):
            builds.append((checkout, destination))
        tarballBuilder = BuildTarballsScript()
        tarballBuilder.buildAllTarballs = myBuilder

        tarballBuilder.main(["checkoutDir", "destinationDir"])
        self.assertEqual(
            builds,
            [(FilePath("checkoutDir"), FilePath("destinationDir"))])


    def test_defaultBuildTarballsScriptBuilder(self):
        """
        The default implementation of L{BuildTarballsScript.buildAllTarballs}
        is L{buildAllTarballs}.
        """
        tarballBuilder = BuildTarballsScript()
        self.assertEqual(tarballBuilder.buildAllTarballs, buildAllTarballs)


    def test_badNumberOfArgumentsToBuildTarballs(self):
        """
        L{BuildTarballsScript.main} raises SystemExit when the wrong number of
        arguments are passed.
        """
        tarballBuilder = BuildTarballsScript()
        self.assertRaises(SystemExit, tarballBuilder.main, [])


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
