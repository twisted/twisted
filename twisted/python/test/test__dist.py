# Copyright (c) 2010 Twisted Matrix Laboratories.
# See LICENSE for details.

import os, stat, errno, tarfile
from xml.dom import minidom as dom
from twisted.trial.unittest import TestCase
from twisted.python.filepath import FilePath

from twisted.python._dist import DocBuilder, ManBuilder, isDistributable
from twisted.python._dist import makeAPIBaseURL, DistributionBuilder
from twisted.python._dist import NoDocumentsFound, filePathDelta
from twisted.python._dist import _stageFile



# When we test that scripts are installed with the "correct" permissions, we
# expect the "correct" permissions to be rwxr-xr-x
SCRIPT_PERMS = (
        stat.S_IRWXU # rwx
        | stat.S_IRGRP | stat.S_IXGRP # r-x
        | stat.S_IROTH | stat.S_IXOTH) # r-x



# Check a bunch of dependencies to skip tests if necessary.
try:
    from twisted.lore.scripts import lore
except ImportError:
    loreSkip = "Lore is not present."
else:
    loreSkip = None



class StructureAssertingMixin(object):
    """
    A mixin for L{TestCase} subclasses which provides some methods for asserting
    the structure and contents of directories and files on the filesystem.
    """
    def createStructure(self, parent, dirDict, origRoot=None):
        """
        Create a set of directories and files given a dict defining their
        structure.

        @param parent: The directory in which to create the structure.  It must
            already exist.
        @type parent: L{FilePath}

        @param dirDict: The dict defining the structure. Keys should be strings
            naming files, values should be strings describing file contents OR
            dicts describing subdirectories.  All files are written in binary
            mode.  Any string values are assumed to describe text files and
            will have their newlines replaced with the platform-native newline
            convention.  For example::

                {"foofile": "foocontents",
                 "bardir": {"barfile": "bar\ncontents"}}
        @type dirDict: C{dict}

        @param origRoot: The directory provided as C{parent} in the original
            invocation of C{createStructure}. Leave this as C{None}, it's used
            in recursion.
        @type origRoot: L{FilePath} or C{None}
        """
        if origRoot is None:
            origRoot = parent

        for x in dirDict:
            child = parent.child(x)
            if isinstance(dirDict[x], dict):
                child.createDirectory()
                self.createStructure(child, dirDict[x], origRoot=origRoot)

                # If x is in a bin directory, make sure children
                # representing files have the executable bit set.
                if "bin" in child.segmentsFrom(origRoot):
                    for script in [k for (k,v) in dirDict[x].items()
                            if isinstance(v, basestring)]:
                        scriptPath = child.child(script)
                        scriptPath.chmod(SCRIPT_PERMS)

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

                # If x is in a bin directory, make sure children
                # representing files have the executable bit set.
                if "/bin" in child.path:
                    for script in [k for (k,v) in dirDict[x].items()
                            if isinstance(v, basestring)]:
                        scriptPath = child.child(script)
                        scriptPath.restat()
                        # What with SVN and umask and all that jazz, all we can
                        # really check is that these scripts have at least one
                        # executable bit set.
                        self.assertTrue(scriptPath.statinfo.st_mode &
                                (stat.S_IXUSR|stat.S_IXGRP|stat.S_IXOTH),
                                "File %r should be executable"
                                % (scriptPath.path,))
            else:
                a = child.getContent().replace(os.linesep, '\n')
                self.assertEquals(a, dirDict[x], child.path)
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
        self.assertEquals(output, expected)


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


    def test_stageFileStagesFiles(self):
        """
        L{_stageFile} duplicates the content and metadata of the given file.
        """
        # Make a test file
        inputFile = self.rootDir.child("foo")

        # Put some content in it.
        inputFile.setContent("bar")

        # Put a funny mode on it.
        modeReadOnly = stat.S_IRUSR|stat.S_IRGRP|stat.S_IROTH
        inputFile.chmod(modeReadOnly)

        # Test the first: stage the file into an existing directory.
        outputFile1 = self.outputDir.child("foo")

        # Test the second: stage the file into a new directory.
        outputFile2 = self.outputDir.preauthChild("sub/dir/foo")

        for outputFile in [outputFile1, outputFile2]:
            _stageFile(inputFile, outputFile)

            # Check the contents of the staged file
            self.failUnlessEqual(outputFile.open("r").read(), "bar")

            # Check the mode of the staged file
            outputFile.restat()
            self.assertEqual(outputFile.statinfo.st_mode,
                    (modeReadOnly | stat.S_IFREG))


    def test_stageFileWillNotOverwrite(self):
        """
        L{_stageFile} raises an exception if asked to overwrite an output file.
        """
        # Make a test file
        inputFile = self.rootDir.child("foo")
        inputFile.setContent("bar")

        # Make an output file.
        outputFile = self.outputDir.child("foo")

        # First attempt should work fine.
        _stageFile(inputFile, outputFile)

        # Second attempt should raise OSError with EEXIST.
        exception = self.failUnlessRaises(OSError, _stageFile, inputFile,
                outputFile)

        self.failUnlessEqual(exception.errno, errno.EEXIST)


    def test_stageFileStagesDirectories(self):
        """
        L{_stageFile} duplicates the content of the given directory.
        """
        # Make a test directory with stuff in it.
        structure = {
            "somedirectory": {
                "somefile": "some content",
                "anotherdirectory": {
                    "anotherfile": "other content"}}}
        self.createStructure(self.rootDir, structure)
        inputDirectory = self.rootDir.child("somedirectory")

        # Stage this directory structure
        outputDirectory = self.outputDir.child("somedirectory")
        _stageFile(inputDirectory, outputDirectory)

        # Check that everything was copied across properly.
        self.assertStructure(self.outputDir, structure)


    def test_stageFileFiltersBytecode(self):
        """
        L{_stageFile} ignores Python bytecode files.
        """
        # Make a test directory with stuff in it.
        inputStructure = {
            "somepackage": {
                "__init__.py": "",
                "__init__.pyc": "gibberish",
                "__init__.pyo": "more gibberish",
                "module.py": "import this",
                "module.pyc": "extra gibberish",
                "module.pyo": "bonus gibberish",
                "datafile.xqz": "A file with an unknown extension"},
            "somemodule.py": "import that",
            "somemodule.pyc": "surplus gibberish",
            "somemodule.pyo": "sundry gibberish"}
        self.createStructure(self.rootDir, inputStructure)

        # Stage this directory structure
        for child in self.rootDir.children():
            dest = self.outputDir.child(child.basename())
            _stageFile(child, dest)

        # Check that everything but bytecode files has been copied across.
        outputStructure = {
            "somepackage": {
                # Ordinary Python files should be copied.
                "__init__.py": "",
                "module.py": "import this",

                # .pyc and .pyc files should be ignored.

                # Other unknown files should be copied too.
                "datafile.xqz": "A file with an unknown extension"},
            # Individually staged files should be copied, unless they're
            # bytecode files.
            "somemodule.py": "import that"}
        self.assertStructure(self.outputDir, outputStructure)


    def test_stageFileFiltersVCSMetadata(self):
        """
        L{_stageFile} ignores common VCS directories.
        """
        # Make a test directory with stuff in it.
        inputStructure = {
            # Twisted's official repository is Subversion.
            ".svn": {
                "svn-data": "some Subversion data"},
            # Twisted has a semi-official bzr mirror of the svn repository.
            ".bzr": {
                "bzr-data": "some Bazaar data"},
            # git-svn is a popular way for git users to deal with svn
            # repositories.
            ".git": {
                "git-data": "some Git data"},
            "somepackage": {
                # Subversion litters its .svn directories everywhere, not just
                # the top-level.
                ".svn": {
                    "svn-data": "more Subversion data"},
                "__init__.py": "",
                "module.py": "import this"},
            "somemodule.py": "import that"}
        self.createStructure(self.rootDir, inputStructure)

        # Stage this directory structure
        for child in self.rootDir.children():
            dest = self.outputDir.child(child.basename())
            _stageFile(child, dest)

        # Check that everything but VCS files has been copied across.
        outputStructure = {
            # No VCS files in the root.
            "somepackage": {
                # Ordinary Python files should be copied.
                "__init__.py": "",
                "module.py": "import this",

                # No VCS files in the package, either.
                },

            # Individually staged files should be copied, unless they're
            # bytecode files.
            "somemodule.py": "import that"}
        self.assertStructure(self.outputDir, outputStructure)


    def test_stageFileHandlesEXDEV(self):
        """
        L{_stageFile} should fall back to copying if os.link raises EXDEV.
        """
        def mock_link(src, dst):
            raise OSError(errno.EXDEV, "dummy error")

        # Mock out os.link so that it always fails with EXDEV.
        self.patch(os, "link", mock_link)

        # Staging a file should still work properly.

        # Make a test file
        inputFile = self.rootDir.child("foo")
        inputFile.setContent("bar")
        modeReadOnly = stat.S_IRUSR|stat.S_IRGRP|stat.S_IROTH
        inputFile.chmod(modeReadOnly)

        # Stage the file into an existing directory.
        outputFile = self.outputDir.child("foo")
        _stageFile(inputFile, outputFile)

        # Check the contents of the staged file
        self.failUnlessEqual(outputFile.open("r").read(), "bar")

        # Check the mode of the staged file
        outputFile.restat()
        self.assertEqual(outputFile.statinfo.st_mode,
                (modeReadOnly | stat.S_IFREG))

    if not getattr(os, "link", None):
        test_stageFileHandlesEXDEV.skip = "OS does not support hard-links"


    def test_twistedDistributionExcludesWeb2AndVFSAndAdmin(self):
        """
        The main Twisted distribution does not include web2 or vfs, or the
        bin/admin directory.
        """
        loreInput, loreOutput = self.getArbitraryLoreInputAndOutput("10.0.0")
        coreIndexInput, coreIndexOutput = self.getArbitraryLoreInputAndOutput(
            "10.0.0", prefix="howto/")

        structure = {
            "README": "Twisted",
            "unrelated": "x",
            "LICENSE": "copyright!",
            "setup.py": "import toplevel",
            "bin": {"web2": {"websetroot": "SET ROOT"},
                    "vfs": {"vfsitup": "hee hee"},
                    "twistd": "TWISTD",
                    "admin": {"build-a-thing": "yay"}},
            "twisted":
                {"web2":
                     {"__init__.py": "import WEB",
                      "topfiles": {"setup.py": "import WEBINSTALL",
                                   "README": "WEB!"}},
                 "vfs":
                     {"__init__.py": "import VFS",
                      "blah blah": "blah blah"},
                 "words": {"__init__.py": "import WORDS"},
                 "plugins": {"twisted_web.py": "import WEBPLUG",
                             "twisted_words.py": "import WORDPLUG",
                             "twisted_web2.py": "import WEB2",
                             "twisted_vfs.py": "import VFS"}},
            "doc": {"web2": {"excluded!": "yay"},
                    "vfs": {"unrelated": "whatever"},
                    "core": {"howto": {"template.tpl": self.template},
                             "index.xhtml": coreIndexInput}}}

        outStructure = {
            "README": "Twisted",
            "unrelated": "x",
            "LICENSE": "copyright!",
            "setup.py": "import toplevel",
            "bin": {"twistd": "TWISTD"},
            "twisted":
                {"words": {"__init__.py": "import WORDS"},
                 "plugins": {"twisted_web.py": "import WEBPLUG",
                             "twisted_words.py": "import WORDPLUG"}},
            "doc": {"core": {"howto": {"template.tpl": self.template},
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
        L{DistributionBuilder.buildSubProject} works with minimal subprojects.
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
        L{DistributionBuilder} builds documentation with the specified
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



class IsDistributableTest(TestCase):
    """
    Tests for L{isDistributable}.
    """


    def test_fixedNamesExcluded(self):
        """
        L{isDistributable} denies certain fixed names from being packaged.
        """
        self.failUnlessEqual(isDistributable(FilePath("foo/_darcs")), False)


    def test_hiddenFilesExcluded(self):
        """
        L{isDistributable} denies names beginning with a ".".
        """
        self.failUnlessEqual(isDistributable(FilePath("foo/.svn")), False)


    def test_byteCodeFilesExcluded(self):
        """
        L{isDistributable} denies Python bytecode files.
        """
        self.failUnlessEqual(isDistributable(FilePath("foo/bar.pyc")), False)
        self.failUnlessEqual(isDistributable(FilePath("foo/bar.pyo")), False)


    def test_otherFilesIncluded(self):
        """
        L{isDistributable} allows files with other names.
        """
        self.failUnlessEqual(isDistributable(FilePath("foo/bar.py")), True)
        self.failUnlessEqual(isDistributable(FilePath("foo/README")), True)
        self.failUnlessEqual(isDistributable(FilePath("foo/twisted")), True)



class MakeAPIBaseURLTest(TestCase):
    """
    Tests for L{makeAPIBaseURL}.
    """


    def test_makeAPIBaseURLIsSubstitutable(self):
        """
        L{makeAPIBaseURL} has a place to subtitute an API name.
        """
        template = makeAPIBaseURL("12.34")

        # Substitute in an API name.
        url = template % ("sasquatch",)

        self.assertEqual(url,
                "http://twistedmatrix.com/documents/12.34/api/sasquatch.html")



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


    def test_filePathDeltaSimilarEndElements(self):
        """
        L{filePathDelta} doesn't take into account final elements when
        comparing 2 paths, but stops at the first difference.
        """
        self.assertEquals(filePathDelta(FilePath("/foo/bar/bar/spam"),
                                        FilePath("/foo/bar/baz/spam")),
                          ["..", "..", "baz", "spam"])
