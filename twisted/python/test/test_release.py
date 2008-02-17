import operator
import os
from twisted.trial.unittest import TestCase

from datetime import date

from twisted.internet import reactor
from twisted.python import release, log
from twisted.python.filepath import FilePath
from twisted.python.util import dsu
from twisted.python.versions import Version
from twisted.python._release import _changeVersionInFile, getNextVersion
from twisted.python._release import findTwistedProjects, replaceInFile
from twisted.python._release import replaceProjectVersion
from twisted.python._release import updateTwistedVersionInformation, Project
from twisted.python._release import VERSION_OFFSET, DocBuilder
from twisted.python._release import NoDocumentsFound, filePathDelta


class ChangeVersionTest(TestCase):
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
        self.assertEquals(getNextVersion(version, now=now),
                          Version("twisted", major, 10, 0))


    def test_getNextVersionAfterYearChange(self):
        """
        When calculating the next version to release when a release is
        happening in a later year, the minor version number is reset to 0.
        """
        now = date.today()
        major = now.year - VERSION_OFFSET
        version = Version("twisted", major - 1, 9, 0)
        self.assertEquals(getNextVersion(version, now=now),
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



class ProjectTest(TestCase):
    """
    There is a first-class representation of a project.
    """

    def assertProjectsEqual(self, observedProjects, expectedProjects):
        """
        Assert that two lists of L{Project}s are equal.
        """
        self.assertEqual(len(observedProjects), len(expectedProjects))
        observedProjects = dsu(observedProjects,
                               key=operator.attrgetter('directory'))
        expectedProjects = dsu(expectedProjects,
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
            version.package, directory.child('_version.py').path,
            (version.major, version.minor, version.micro))
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
        self.assertEquals(project.getVersion(), version)


    def test_updateVersion(self):
        """
        Project objects know how to update the version numbers in those
        projects.
        """
        project = self.makeProject(Version("bar", 2, 1, 0))
        newVersion = Version("bar", 3, 2, 9)
        project.updateVersion(newVersion)
        self.assertEquals(project.getVersion(), newVersion)
        self.assertEquals(
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
        self.assertEquals(cwd, os.getcwd())



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
        self.assertEquals(open('release.replace').read(), expected)


        expected = expected.replace('2.0.0', '3.0.0')
        replaceInFile('release.replace', {'2.0.0': '3.0.0'})
        self.assertEquals(open('release.replace').read(), expected)



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
        replaceProjectVersion("twisted.test_project",
                              "test_project", [0, 82, 7])
        ns = {'__name___': 'twisted.test_project'}
        execfile("test_project", ns)
        self.assertEquals(ns["version"].base(), "0.82.7")


class DocBuilderTestCase(TestCase):
    """
    Tests for L{DocBuilder}.

    Note for future maintainers: The exact byte equality assertions throughout
    this suite may need to be updated due to minor differences in lore. They
    should not be taken to mean that Lore must maintain the same byte format
    forever. Feel free to update the tests when Lore changes, but please be
    careful.
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
        Set up a few instance variables that will be useful.

        @ivar builder: A plain L{DocBuilder}.
        @ivar docCounter: An integer to be used as a counter by the
            C{getArbitrary...} methods.
        @ivar howtoDir: A L{FilePath} representing a directory to be used for
            containing Lore documents.
        @ivar templateFile: A L{FilePath} representing a file with
            C{self.template} as its content.
        """
        self.builder = DocBuilder()
        self.docCounter = 0
        self.howtoDir = FilePath(self.mktemp())
        self.howtoDir.createDirectory()
        self.templateFile = self.howtoDir.child("template.tpl")
        self.templateFile.setContent(self.template)


    def getArbitraryLoreInput(self):
        """
        Get an arbitrary, unique (for this test case) string of lore input.
        """
        template = (
            '<html><head><title>Hi! %(count)s</title></head>'
            '<body>Hi! %(count)s</body></html>')
        return template % {"count": self.docCounter}


    def getArbitraryLoreInputAndOutput(self, version):
        """
        Get an input document along with expected output for lore run on that
        output document, assuming an appropriately-specified C{self.template}.

        @return: A two-tuple of input and expected output.
        @rtype: C{(str, str)}.
        """
        self.docCounter += 1
        return (self.getArbitraryLoreInput(),
                '<?xml version="1.0"?>'
                '<html><head><title>Yo:Hi! %(count)s</title></head>'
                '<body><div class="content">Hi! %(count)s</div>'
                '<a href="index.html">Index</a>'
                '<span class="version">Version: %(version)s</span>'
                '</body></html>'
                % {"count": self.docCounter, "version": version})


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
        self.assertEquals(out1.getContent(), output1)
        self.assertEquals(out2.getContent(), output2)


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
        input = self.getArbitraryLoreInput()
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
        input = self.getArbitraryLoreInput()
        resourceDir = self.howtoDir.child("resources")
        docDir = self.howtoDir.child("docs")
        docDir.createDirectory()
        docDir.child("child.xhtml").setContent(input)
        self.builder.build("1.2.3", resourceDir, docDir, self.templateFile)
        outFile = docDir.child('child.html')
        self.assertIn('<a href="../resources/index.html">Index</a>',
                      outFile.getContent())


    def test_deleteInput(self):
        """
        L{DocBuilder.build} can be instructed to delete the input files after
        generating the output based on them.
        """
        input1 = self.getArbitraryLoreInput()
        self.howtoDir.child("one.xhtml").setContent(input1)
        self.builder.build("whatever", self.howtoDir, self.howtoDir,
                           self.templateFile, deleteInput=True)
        self.assertTrue(self.howtoDir.child('one.html').exists())
        self.assertFalse(self.howtoDir.child('one.xhtml').exists())


    def test_doNotDeleteInput(self):
        """
        Input will not be deleted by default.
        """
        input1 = self.getArbitraryLoreInput()
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
        self.assertEquals(linkrel, "")


    def test_getLinkrelToParentDirectory(self):
        """
        If the doc directory is a child of the resource directory, the linkrel
        should make use of '..'.
        """
        linkrel = self.builder.getLinkrel(FilePath("/foo"),
                                          FilePath("/foo/bar"))
        self.assertEquals(linkrel, "../")


    def test_getLinkrelToSibling(self):
        """
        If the doc directory is a sibling of the resource directory, the
        linkrel should make use of '..' and a named segment.
        """
        linkrel = self.builder.getLinkrel(FilePath("/foo/howto"),
                                          FilePath("/foo/examples"))
        self.assertEquals(linkrel, "../howto/")


    def test_getLinkrelToUncle(self):
        """
        If the doc directory is a sibling of the parent of the resource
        directory, the linkrel should make use of multiple '..'s and a named
        segment.
        """
        linkrel = self.builder.getLinkrel(FilePath("/foo/howto"),
                                          FilePath("/foo/examples/quotes"))
        self.assertEquals(linkrel, "../../howto/")



class FilePathDeltaTest(TestCase):
    """
    Tests for L{filePathDelta}.
    """

    def test_filePathDeltaSubdir(self):
        """
        L{filePathDelta} can create a simple relative path to a child path.
        """
        self.assertEquals(filePathDelta(FilePath("/foo/bar"),
                                        FilePath("/foo/bar/baz")),
                          ["baz"])


    def test_filePathDeltaSiblingDir(self):
        """
        L{filePathDelta} can traverse upwards to create relative paths to
        siblings.
        """
        self.assertEquals(filePathDelta(FilePath("/foo/bar"),
                                        FilePath("/foo/baz")),
                          ["..", "baz"])


    def test_filePathNoCommonElements(self):
        """
        L{filePathDelta} can create relative paths to totally unrelated paths
        for maximum portability.
        """
        self.assertEquals(filePathDelta(FilePath("/foo/bar"),
                                        FilePath("/baz/quux")),
                          ["..", "..", "baz", "quux"])


