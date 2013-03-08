# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# ++ single anchor added to individual output file
# ++ two anchors added to individual output file
# ++ anchors added to individual output files
# ++ entry added to index
# ++ index entry pointing to correct file and anchor
# ++ multiple entries added to index
# ++ multiple index entries pointing to correct files and anchors
# __ all of above for files in deep directory structure
#
# ++ group index entries by indexed term
# ++ sort index entries by indexed term
# __ hierarchical index entries (e.g. language!programming)
#
# ++ add parameter for what the index filename should be
# ++ add (default) ability to NOT index (if index not specified)
#
# ++ put actual index filename into INDEX link (if any) in the template
# __ make index links RELATIVE!
# __ make index pay attention to the outputdir!
#
# __ make index look nice
#
# ++ add section numbers to headers in lore output
# ++ make text of index entry links be chapter numbers
# ++ make text of index entry links be section numbers
#
# __ put all of our test files someplace neat and tidy
#

import os, shutil, errno, time
from StringIO import StringIO
from xml.dom import minidom as dom

from twisted.trial import unittest
from twisted.python.filepath import FilePath

from twisted.lore import tree, process, indexer, numberer, htmlbook, default
from twisted.lore.default import factory
from twisted.lore.latex import LatexSpitter

from twisted.python.util import sibpath

from twisted.lore.scripts import lore

from twisted.web import domhelpers

def sp(originalFileName):
    return sibpath(__file__, originalFileName)

options = {"template" : sp("template.tpl"), 'baseurl': '%s', 'ext': '.xhtml' }
d = options


class _XMLAssertionMixin:
    """
    Test mixin defining a method for comparing serialized XML documents.
    """
    def assertXMLEqual(self, first, second):
        """
        Verify that two strings represent the same XML document.
        """
        self.assertEqual(
            dom.parseString(first).toxml(),
            dom.parseString(second).toxml())


class TestFactory(unittest.TestCase, _XMLAssertionMixin):

    file = sp('simple.html')
    linkrel = ""

    def assertEqualFiles1(self, exp, act):
        if (exp == act): return True
        fact = open(act)
        self.assertEqualsFile(exp, fact.read())

    def assertEqualFiles(self, exp, act):
        if (exp == act): return True
        fact = open(sp(act))
        self.assertEqualsFile(exp, fact.read())

    def assertEqualsFile(self, exp, act):
        expected = open(sp(exp)).read()
        self.assertEqual(expected, act)

    def makeTemp(self, *filenames):
        tmp = self.mktemp()
        os.mkdir(tmp)
        for filename in filenames:
            tmpFile = os.path.join(tmp, filename)
            shutil.copyfile(sp(filename), tmpFile)
        return tmp

########################################

    def setUp(self):
        indexer.reset()
        numberer.reset()

    def testProcessingFunctionFactory(self):
        base = FilePath(self.mktemp())
        base.makedirs()

        simple = base.child('simple.html')
        FilePath(__file__).sibling('simple.html').copyTo(simple)

        htmlGenerator = factory.generate_html(options)
        htmlGenerator(simple.path, self.linkrel)

        self.assertXMLEqual(
            """\
<?xml version="1.0" ?><!DOCTYPE html  PUBLIC '-//W3C//DTD XHTML 1.0 Transitional//EN'  'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd'><html lang="en" xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Twisted Documentation: My Test Lore Input</title></head>
  <body bgcolor="white">
    <h1 class="title">My Test Lore Input</h1>
    <div class="content">
<span/>
<p>A Body.</p>
</div>
    <a href="index.xhtml">Index</a>
  </body>
</html>""",
            simple.sibling('simple.xhtml').getContent())


    def testProcessingFunctionFactoryWithFilenameGenerator(self):
        base = FilePath(self.mktemp())
        base.makedirs()

        def filenameGenerator(originalFileName, outputExtension):
            name = os.path.splitext(FilePath(originalFileName).basename())[0]
            return base.child(name + outputExtension).path

        htmlGenerator = factory.generate_html(options, filenameGenerator)
        htmlGenerator(self.file, self.linkrel)
        self.assertXMLEqual(
            """\
<?xml version="1.0" ?><!DOCTYPE html  PUBLIC '-//W3C//DTD XHTML 1.0 Transitional//EN'  'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd'><html lang="en" xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Twisted Documentation: My Test Lore Input</title></head>
  <body bgcolor="white">
    <h1 class="title">My Test Lore Input</h1>
    <div class="content">
<span/>
<p>A Body.</p>
</div>
    <a href="index.xhtml">Index</a>
  </body>
</html>""",
            base.child("simple.xhtml").getContent())


    def test_doFile(self):
        base = FilePath(self.mktemp())
        base.makedirs()

        simple = base.child('simple.html')
        FilePath(__file__).sibling('simple.html').copyTo(simple)

        templ = dom.parse(open(d['template']))

        tree.doFile(simple.path, self.linkrel, d['ext'], d['baseurl'], templ, d)
        self.assertXMLEqual(
            """\
<?xml version="1.0" ?><!DOCTYPE html  PUBLIC '-//W3C//DTD XHTML 1.0 Transitional//EN'  'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd'><html lang="en" xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Twisted Documentation: My Test Lore Input</title></head>
  <body bgcolor="white">
    <h1 class="title">My Test Lore Input</h1>
    <div class="content">
<span/>
<p>A Body.</p>
</div>
    <a href="index.xhtml">Index</a>
  </body>
</html>""",
            base.child("simple.xhtml").getContent())


    def test_doFile_withFilenameGenerator(self):
        base = FilePath(self.mktemp())
        base.makedirs()

        def filenameGenerator(originalFileName, outputExtension):
            name = os.path.splitext(FilePath(originalFileName).basename())[0]
            return base.child(name + outputExtension).path

        templ = dom.parse(open(d['template']))
        tree.doFile(self.file, self.linkrel, d['ext'], d['baseurl'], templ, d, filenameGenerator)

        self.assertXMLEqual(
            """\
<?xml version="1.0" ?><!DOCTYPE html  PUBLIC '-//W3C//DTD XHTML 1.0 Transitional//EN'  'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd'><html lang="en" xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Twisted Documentation: My Test Lore Input</title></head>
  <body bgcolor="white">
    <h1 class="title">My Test Lore Input</h1>
    <div class="content">
<span/>
<p>A Body.</p>
</div>
    <a href="index.xhtml">Index</a>
  </body>
</html>""",
            base.child("simple.xhtml").getContent())


    def test_munge(self):
        indexer.setIndexFilename("lore_index_file.html")
        doc = dom.parse(open(self.file))
        node = dom.parse(open(d['template']))
        tree.munge(doc, node, self.linkrel,
                   os.path.dirname(self.file),
                   self.file,
                   d['ext'], d['baseurl'], d)

        self.assertXMLEqual(
            """\
<?xml version="1.0" ?><!DOCTYPE html  PUBLIC '-//W3C//DTD XHTML 1.0 Transitional//EN'  'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd'><html lang="en" xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Twisted Documentation: My Test Lore Input</title></head>
  <body bgcolor="white">
    <h1 class="title">My Test Lore Input</h1>
    <div class="content">
<span/>
<p>A Body.</p>
</div>
    <a href="lore_index_file.html">Index</a>
  </body>
</html>""",
            node.toxml())


    def test_mungeAuthors(self):
        """
        If there is a node with a I{class} attribute set to C{"authors"},
        L{tree.munge} adds anchors as children to it, takeing the necessary
        information from any I{link} nodes in the I{head} with their I{rel}
        attribute set to C{"author"}.
        """
        document = dom.parseString(
            """\
<html>
  <head>
    <title>munge authors</title>
    <link rel="author" title="foo" href="bar"/>
    <link rel="author" title="baz" href="quux"/>
    <link rel="author" title="foobar" href="barbaz"/>
  </head>
  <body>
    <h1>munge authors</h1>
  </body>
</html>""")
        template = dom.parseString(
            """\
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
  <head>
    <title />
  </head>

  <body>
    <div class="body" />
    <div class="authors" />
  </body>
</html>
""")
        tree.munge(
            document, template, self.linkrel, os.path.dirname(self.file),
            self.file, d['ext'], d['baseurl'], d)

        self.assertXMLEqual(
            template.toxml(),
            """\
<?xml version="1.0" ?><html lang="en" xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <title>munge authors</title>
  <link href="bar" rel="author" title="foo"/><link href="quux" rel="author" title="baz"/><link href="barbaz" rel="author" title="foobar"/></head>

  <body>
    <div class="content">
    <span/>
  </div>
    <div class="authors"><span><a href="bar">foo</a>, <a href="quux">baz</a>, and <a href="barbaz">foobar</a></span></div>
  </body>
</html>""")


    def test_getProcessor(self):

        base = FilePath(self.mktemp())
        base.makedirs()
        input = base.child("simple3.html")
        FilePath(__file__).sibling("simple3.html").copyTo(input)

        options = { 'template': sp('template.tpl'), 'ext': '.xhtml', 'baseurl': 'burl',
                    'filenameMapping': None }
        p = process.getProcessor(default, "html", options)
        p(input.path, self.linkrel)
        self.assertXMLEqual(
            """\
<?xml version="1.0" ?><!DOCTYPE html  PUBLIC '-//W3C//DTD XHTML 1.0 Transitional//EN'  'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd'><html lang="en" xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Twisted Documentation: My Test Lore Input</title></head>
  <body bgcolor="white">
    <h1 class="title">My Test Lore Input</h1>
    <div class="content">
<span/>
<p>A Body.</p>
</div>
    <a href="index.xhtml">Index</a>
  </body>
</html>""",
            base.child("simple3.xhtml").getContent())

    def test_outputdirGenerator(self):
        normp = os.path.normpath; join = os.path.join
        inputdir  = normp(join("/", 'home', 'joe'))
        outputdir = normp(join("/", 'away', 'joseph'))
        actual = process.outputdirGenerator(join("/", 'home', 'joe', "myfile.html"),
                                            '.xhtml', inputdir, outputdir)
        expected = normp(join("/", 'away', 'joseph', 'myfile.xhtml'))
        self.assertEqual(expected, actual)

    def test_outputdirGeneratorBadInput(self):
        options = {'outputdir': '/away/joseph/', 'inputdir': '/home/joe/' }
        self.assertRaises(ValueError, process.outputdirGenerator, '.html', '.xhtml', **options)

    def test_makeSureDirectoryExists(self):
        dirname = os.path.join("tmp", 'nonexistentdir')
        if os.path.exists(dirname):
            os.rmdir(dirname)
        self.failIf(os.path.exists(dirname), "Hey: someone already created the dir")
        filename = os.path.join(dirname, 'newfile')
        tree.makeSureDirectoryExists(filename)
        self.failUnless(os.path.exists(dirname), 'should have created dir')
        os.rmdir(dirname)


    def test_indexAnchorsAdded(self):
        indexer.setIndexFilename('theIndexFile.html')
        # generate the output file
        templ = dom.parse(open(d['template']))
        tmp = self.makeTemp('lore_index_test.xhtml')

        tree.doFile(os.path.join(tmp, 'lore_index_test.xhtml'),
                    self.linkrel, '.html', d['baseurl'], templ, d)

        self.assertXMLEqual(
            """\
<?xml version="1.0" ?><!DOCTYPE html  PUBLIC '-//W3C//DTD XHTML 1.0 Transitional//EN'  'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd'><html lang="en" xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Twisted Documentation: The way of the program</title></head>
  <body bgcolor="white">
    <h1 class="title">The way of the program</h1>
    <div class="content">

<span/>

<p>The first paragraph.</p>


<h2>The Python programming language<a name="auto0"/></h2>
<a name="index01"/>
<a name="index02"/>

<p>The second paragraph.</p>


</div>
    <a href="theIndexFile.html">Index</a>
  </body>
</html>""",
            FilePath(tmp).child("lore_index_test.html").getContent())


    def test_indexEntriesAdded(self):
        indexer.addEntry('lore_index_test.html', 'index02', 'language of programming', '1.3')
        indexer.addEntry('lore_index_test.html', 'index01', 'programming language', '1.2')
        indexer.setIndexFilename("lore_index_file.html")
        indexer.generateIndex()
        self.assertEqualFiles1("lore_index_file_out.html", "lore_index_file.html")

    def test_book(self):
        tmp = self.makeTemp()
        inputFilename = sp('lore_index_test.xhtml')

        bookFilename = os.path.join(tmp, 'lore_test_book.book')
        bf = open(bookFilename, 'w')
        bf.write('Chapter(r"%s", None)\r\n' % inputFilename)
        bf.close()

        book = htmlbook.Book(bookFilename)
        expected = {'indexFilename': None,
                    'chapters': [(inputFilename, None)],
                    }
        dct = book.__dict__
        for k in dct:
            self.assertEqual(dct[k], expected[k])

    def test_runningLore(self):
        options = lore.Options()
        tmp = self.makeTemp('lore_index_test.xhtml')

        templateFilename = sp('template.tpl')
        inputFilename = os.path.join(tmp, 'lore_index_test.xhtml')
        indexFilename = 'theIndexFile'

        bookFilename = os.path.join(tmp, 'lore_test_book.book')
        bf = open(bookFilename, 'w')
        bf.write('Chapter(r"%s", None)\n' % inputFilename)
        bf.close()

        options.parseOptions(['--null', '--book=%s' % bookFilename,
                              '--config', 'template=%s' % templateFilename,
                              '--index=%s' % indexFilename
                              ])
        result = lore.runGivenOptions(options)
        self.assertEqual(None, result)
        self.assertEqualFiles1("lore_index_file_unnumbered_out.html", indexFilename + ".html")


    def test_runningLoreMultipleFiles(self):
        tmp = self.makeTemp('lore_index_test.xhtml', 'lore_index_test2.xhtml')
        templateFilename = sp('template.tpl')
        inputFilename = os.path.join(tmp, 'lore_index_test.xhtml')
        inputFilename2 = os.path.join(tmp, 'lore_index_test2.xhtml')
        indexFilename = 'theIndexFile'

        bookFilename = os.path.join(tmp, 'lore_test_book.book')
        bf = open(bookFilename, 'w')
        bf.write('Chapter(r"%s", None)\n' % inputFilename)
        bf.write('Chapter(r"%s", None)\n' % inputFilename2)
        bf.close()

        options = lore.Options()
        options.parseOptions(['--null', '--book=%s' % bookFilename,
                              '--config', 'template=%s' % templateFilename,
                              '--index=%s' % indexFilename
                              ])
        result = lore.runGivenOptions(options)
        self.assertEqual(None, result)

        self.assertEqual(
            # XXX This doesn't seem like a very good index file.
            """\
aahz: <a href="lore_index_test2.html#index03">link</a><br />
aahz2: <a href="lore_index_test2.html#index02">link</a><br />
language of programming: <a href="lore_index_test.html#index02">link</a>, <a href="lore_index_test2.html#index01">link</a><br />
programming language: <a href="lore_index_test.html#index01">link</a><br />
""",
            file(FilePath(indexFilename + ".html").path).read())

        self.assertXMLEqual(
            """\
<?xml version="1.0" ?><!DOCTYPE html  PUBLIC '-//W3C//DTD XHTML 1.0 Transitional//EN'  'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd'><html lang="en" xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Twisted Documentation: The way of the program</title></head>
  <body bgcolor="white">
    <h1 class="title">The way of the program</h1>
    <div class="content">

<span/>

<p>The first paragraph.</p>


<h2>The Python programming language<a name="auto0"/></h2>
<a name="index01"/>
<a name="index02"/>

<p>The second paragraph.</p>


</div>
    <a href="theIndexFile.html">Index</a>
  </body>
</html>""",
            FilePath(tmp).child("lore_index_test.html").getContent())

        self.assertXMLEqual(
            """\
<?xml version="1.0" ?><!DOCTYPE html  PUBLIC '-//W3C//DTD XHTML 1.0 Transitional//EN'  'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd'><html lang="en" xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Twisted Documentation: The second page to index</title></head>
  <body bgcolor="white">
    <h1 class="title">The second page to index</h1>
    <div class="content">

<span/>

<p>The first paragraph of the second page.</p>


<h2>The Jython programming language<a name="auto0"/></h2>
<a name="index01"/>
<a name="index02"/>
<a name="index03"/>

<p>The second paragraph of the second page.</p>


</div>
    <a href="theIndexFile.html">Index</a>
  </body>
</html>""",
            FilePath(tmp).child("lore_index_test2.html").getContent())



    def XXXtest_NumberedSections(self):
        # run two files through lore, with numbering turned on
        # every h2 should be numbered:
        # first  file's h2s should be 1.1, 1.2
        # second file's h2s should be 2.1, 2.2
        templateFilename = sp('template.tpl')
        inputFilename = sp('lore_numbering_test.xhtml')
        inputFilename2 = sp('lore_numbering_test2.xhtml')
        indexFilename = 'theIndexFile'

        # you can number without a book:
        options = lore.Options()
        options.parseOptions(['--null',
                              '--index=%s' % indexFilename,
                              '--config', 'template=%s' % templateFilename,
                              '--config', 'ext=%s' % ".tns",
                              '--number',
                              inputFilename, inputFilename2])
        result = lore.runGivenOptions(options)

        self.assertEqual(None, result)
        #self.assertEqualFiles1("lore_index_file_out_multiple.html", indexFilename + ".tns")
        #                       VVV change to new, numbered files
        self.assertEqualFiles("lore_numbering_test_out.html", "lore_numbering_test.tns")
        self.assertEqualFiles("lore_numbering_test_out2.html", "lore_numbering_test2.tns")


    def test_setTitle(self):
        """
        L{tree.setTitle} inserts the given title into the first I{title}
        element and the first element with the I{title} class in the given
        template.
        """
        parent = dom.Element('div')
        firstTitle = dom.Element('title')
        parent.appendChild(firstTitle)
        secondTitle = dom.Element('span')
        secondTitle.setAttribute('class', 'title')
        parent.appendChild(secondTitle)

        titleNodes = [dom.Text()]
        # minidom has issues with cloning documentless-nodes.  See Python issue
        # 4851.
        titleNodes[0].ownerDocument = dom.Document()
        titleNodes[0].data = 'foo bar'

        tree.setTitle(parent, titleNodes, None)
        self.assertEqual(firstTitle.toxml(), '<title>foo bar</title>')
        self.assertEqual(
            secondTitle.toxml(), '<span class="title">foo bar</span>')


    def test_setTitleWithChapter(self):
        """
        L{tree.setTitle} includes a chapter number if it is passed one.
        """
        document = dom.Document()

        parent = dom.Element('div')
        parent.ownerDocument = document

        title = dom.Element('title')
        parent.appendChild(title)

        titleNodes = [dom.Text()]
        titleNodes[0].ownerDocument = document
        titleNodes[0].data = 'foo bar'

        # Oh yea.  The numberer has to agree to put the chapter number in, too.
        numberer.setNumberSections(True)

        tree.setTitle(parent, titleNodes, '13')
        self.assertEqual(title.toxml(), '<title>13. foo bar</title>')


    def test_setIndexLink(self):
        """
        Tests to make sure that index links are processed when an index page
        exists and removed when there is not.
        """
        templ = dom.parse(open(d['template']))
        indexFilename = 'theIndexFile'
        numLinks = len(domhelpers.findElementsWithAttribute(templ,
                                                            "class",
                                                            "index-link"))

        # if our testing template has no index-link nodes, complain about it
        self.assertNotEquals(
            [],
            domhelpers.findElementsWithAttribute(templ,
                                                 "class",
                                                 "index-link"))

        tree.setIndexLink(templ, indexFilename)

        self.assertEqual(
            [],
            domhelpers.findElementsWithAttribute(templ,
                                                 "class",
                                                 "index-link"))

        indexLinks = domhelpers.findElementsWithAttribute(templ,
                                                          "href",
                                                          indexFilename)
        self.assertTrue(len(indexLinks) >= numLinks)

        templ = dom.parse(open(d['template']))
        self.assertNotEquals(
            [],
            domhelpers.findElementsWithAttribute(templ,
                                                 "class",
                                                 "index-link"))
        indexFilename = None

        tree.setIndexLink(templ, indexFilename)

        self.assertEqual(
            [],
            domhelpers.findElementsWithAttribute(templ,
                                                 "class",
                                                 "index-link"))


    def test_addMtime(self):
        """
        L{tree.addMtime} inserts a text node giving the last modification time
        of the specified file wherever it encounters an element with the
        I{mtime} class.
        """
        path = FilePath(self.mktemp())
        path.setContent('')
        when = time.ctime(path.getModificationTime())

        parent = dom.Element('div')
        mtime = dom.Element('span')
        mtime.setAttribute('class', 'mtime')
        parent.appendChild(mtime)

        tree.addMtime(parent, path.path)
        self.assertEqual(
            mtime.toxml(), '<span class="mtime">' + when + '</span>')


    def test_makeLineNumbers(self):
        """
        L{tree._makeLineNumbers} takes an integer and returns a I{p} tag with
        that number of line numbers in it.
        """
        numbers = tree._makeLineNumbers(1)
        self.assertEqual(numbers.tagName, 'p')
        self.assertEqual(numbers.getAttribute('class'), 'py-linenumber')
        self.assertIsInstance(numbers.firstChild, dom.Text)
        self.assertEqual(numbers.firstChild.nodeValue, '1\n')

        numbers = tree._makeLineNumbers(10)
        self.assertEqual(numbers.tagName, 'p')
        self.assertEqual(numbers.getAttribute('class'), 'py-linenumber')
        self.assertIsInstance(numbers.firstChild, dom.Text)
        self.assertEqual(
            numbers.firstChild.nodeValue,
            ' 1\n 2\n 3\n 4\n 5\n'
            ' 6\n 7\n 8\n 9\n10\n')


    def test_fontifyPythonNode(self):
        """
        L{tree.fontifyPythonNode} accepts a text node and replaces it in its
        parent with a syntax colored and line numbered version of the Python
        source it contains.
        """
        parent = dom.Element('div')
        source = dom.Text()
        source.data = 'def foo():\n    pass\n'
        parent.appendChild(source)

        tree.fontifyPythonNode(source)

        expected = """\
<div><pre class="python"><p class="py-linenumber">1
2
</p><span class="py-src-keyword">def</span> <span class="py-src-identifier">foo</span>():
    <span class="py-src-keyword">pass</span>
</pre></div>"""

        self.assertEqual(parent.toxml(), expected)


    def test_addPyListings(self):
        """
        L{tree.addPyListings} accepts a document with nodes with their I{class}
        attribute set to I{py-listing} and replaces those nodes with Python
        source listings from the file given by the node's I{href} attribute.
        """
        listingPath = FilePath(self.mktemp())
        listingPath.setContent('def foo():\n    pass\n')

        parent = dom.Element('div')
        listing = dom.Element('a')
        listing.setAttribute('href', listingPath.basename())
        listing.setAttribute('class', 'py-listing')
        parent.appendChild(listing)

        tree.addPyListings(parent, listingPath.dirname())

        expected = """\
<div><div class="py-listing"><pre><p class="py-linenumber">1
2
</p><span class="py-src-keyword">def</span> <span class="py-src-identifier">foo</span>():
    <span class="py-src-keyword">pass</span>
</pre><div class="caption"> - <a href="temp"><span class="filename">temp</span></a></div></div></div>"""

        self.assertEqual(parent.toxml(), expected)


    def test_addPyListingsSkipLines(self):
        """
        If a node with the I{py-listing} class also has a I{skipLines}
        attribute, that number of lines from the beginning of the source
        listing are omitted.
        """
        listingPath = FilePath(self.mktemp())
        listingPath.setContent('def foo():\n    pass\n')

        parent = dom.Element('div')
        listing = dom.Element('a')
        listing.setAttribute('href', listingPath.basename())
        listing.setAttribute('class', 'py-listing')
        listing.setAttribute('skipLines', 1)
        parent.appendChild(listing)

        tree.addPyListings(parent, listingPath.dirname())

        expected = """\
<div><div class="py-listing"><pre><p class="py-linenumber">1
</p>    <span class="py-src-keyword">pass</span>
</pre><div class="caption"> - <a href="temp"><span class="filename">temp</span></a></div></div></div>"""

        self.assertEqual(parent.toxml(), expected)


    def test_fixAPI(self):
        """
        The element passed to L{tree.fixAPI} has all of its children with the
        I{API} class rewritten to contain links to the API which is referred to
        by the text they contain.
        """
        parent = dom.Element('div')
        link = dom.Element('span')
        link.setAttribute('class', 'API')
        text = dom.Text()
        text.data = 'foo'
        link.appendChild(text)
        parent.appendChild(link)

        tree.fixAPI(parent, 'http://example.com/%s')
        self.assertEqual(
            parent.toxml(),
            '<div><span class="API">'
            '<a href="http://example.com/foo" title="foo">foo</a>'
            '</span></div>')


    def test_fixAPIBase(self):
        """
        If a node with the I{API} class and a value for the I{base} attribute
        is included in the DOM passed to L{tree.fixAPI}, the link added to that
        node refers to the API formed by joining the value of the I{base}
        attribute to the text contents of the node.
        """
        parent = dom.Element('div')
        link = dom.Element('span')
        link.setAttribute('class', 'API')
        link.setAttribute('base', 'bar')
        text = dom.Text()
        text.data = 'baz'
        link.appendChild(text)
        parent.appendChild(link)

        tree.fixAPI(parent, 'http://example.com/%s')

        self.assertEqual(
            parent.toxml(),
            '<div><span class="API">'
            '<a href="http://example.com/bar.baz" title="bar.baz">baz</a>'
            '</span></div>')


    def test_fixLinks(self):
        """
        Links in the nodes of the DOM passed to L{tree.fixLinks} have their
        extensions rewritten to the given extension.
        """
        parent = dom.Element('div')
        link = dom.Element('a')
        link.setAttribute('href', 'foo.html')
        parent.appendChild(link)

        tree.fixLinks(parent, '.xhtml')

        self.assertEqual(parent.toxml(), '<div><a href="foo.xhtml"/></div>')


    def test_setVersion(self):
        """
        Nodes of the DOM passed to L{tree.setVersion} which have the I{version}
        class have the given version added to them a child.
        """
        parent = dom.Element('div')
        version = dom.Element('span')
        version.setAttribute('class', 'version')
        parent.appendChild(version)

        tree.setVersion(parent, '1.2.3')

        self.assertEqual(
            parent.toxml(), '<div><span class="version">1.2.3</span></div>')


    def test_footnotes(self):
        """
        L{tree.footnotes} finds all of the nodes with the I{footnote} class in
        the DOM passed to it and adds a footnotes section to the end of the
        I{body} element which includes them.  It also inserts links to those
        footnotes from the original definition location.
        """
        parent = dom.Element('div')
        body = dom.Element('body')
        footnote = dom.Element('span')
        footnote.setAttribute('class', 'footnote')
        text = dom.Text()
        text.data = 'this is the footnote'
        footnote.appendChild(text)
        body.appendChild(footnote)
        body.appendChild(dom.Element('p'))
        parent.appendChild(body)

        tree.footnotes(parent)

        self.assertEqual(
            parent.toxml(),
            '<div><body>'
            '<a href="#footnote-1" title="this is the footnote">'
            '<super>1</super>'
            '</a>'
            '<p/>'
            '<h2>Footnotes</h2>'
            '<ol><li><a name="footnote-1">'
            '<span class="footnote">this is the footnote</span>'
            '</a></li></ol>'
            '</body></div>')


    def test_generateTableOfContents(self):
        """
        L{tree.generateToC} returns an element which contains a table of
        contents generated from the headers in the document passed to it.
        """
        parent = dom.Element('body')
        header = dom.Element('h2')
        text = dom.Text()
        text.data = u'header & special character'
        header.appendChild(text)
        parent.appendChild(header)
        subheader = dom.Element('h3')
        text = dom.Text()
        text.data = 'subheader'
        subheader.appendChild(text)
        parent.appendChild(subheader)

        tableOfContents = tree.generateToC(parent)
        self.assertEqual(
            tableOfContents.toxml(),
            '<ol><li><a href="#auto0">header &amp; special character</a></li><ul><li><a href="#auto1">subheader</a></li></ul></ol>')

        self.assertEqual(
            header.toxml(),
            '<h2>header &amp; special character<a name="auto0"/></h2>')

        self.assertEqual(
            subheader.toxml(),
            '<h3>subheader<a name="auto1"/></h3>')


    def test_putInToC(self):
        """
        L{tree.putInToC} replaces all of the children of the first node with
        the I{toc} class with the given node representing a table of contents.
        """
        parent = dom.Element('div')
        toc = dom.Element('span')
        toc.setAttribute('class', 'toc')
        toc.appendChild(dom.Element('foo'))
        parent.appendChild(toc)

        tree.putInToC(parent, dom.Element('toc'))

        self.assertEqual(toc.toxml(), '<span class="toc"><toc/></span>')


    def test_invalidTableOfContents(self):
        """
        If passed a document with I{h3} elements before any I{h2} element,
        L{tree.generateToC} raises L{ValueError} explaining that this is not a
        valid document.
        """
        parent = dom.Element('body')
        parent.appendChild(dom.Element('h3'))
        err = self.assertRaises(ValueError, tree.generateToC, parent)
        self.assertEqual(
            str(err), "No H3 element is allowed until after an H2 element")


    def test_notes(self):
        """
        L{tree.notes} inserts some additional markup before the first child of
        any node with the I{note} class.
        """
        parent = dom.Element('div')
        noteworthy = dom.Element('span')
        noteworthy.setAttribute('class', 'note')
        noteworthy.appendChild(dom.Element('foo'))
        parent.appendChild(noteworthy)

        tree.notes(parent)

        self.assertEqual(
            noteworthy.toxml(),
            '<span class="note"><strong>Note: </strong><foo/></span>')


    def test_findNodeJustBefore(self):
        """
        L{tree.findNodeJustBefore} returns the previous sibling of the node it
        is passed.  The list of nodes passed in is ignored.
        """
        parent = dom.Element('div')
        result = dom.Element('foo')
        target = dom.Element('bar')
        parent.appendChild(result)
        parent.appendChild(target)

        self.assertIdentical(
            tree.findNodeJustBefore(target, [parent, result]),
            result)

        # Also, support other configurations.  This is a really not nice API.
        newTarget = dom.Element('baz')
        target.appendChild(newTarget)
        self.assertIdentical(
            tree.findNodeJustBefore(newTarget, [parent, result]),
            result)


    def test_getSectionNumber(self):
        """
        L{tree.getSectionNumber} accepts an I{H2} element and returns its text
        content.
        """
        header = dom.Element('foo')
        text = dom.Text()
        text.data = 'foobar'
        header.appendChild(text)
        self.assertEqual(tree.getSectionNumber(header), 'foobar')


    def test_numberDocument(self):
        """
        L{tree.numberDocument} inserts section numbers into the text of each
        header.
        """
        parent = dom.Element('foo')
        section = dom.Element('h2')
        text = dom.Text()
        text.data = 'foo'
        section.appendChild(text)
        parent.appendChild(section)

        tree.numberDocument(parent, '7')

        self.assertEqual(section.toxml(), '<h2>7.1 foo</h2>')


    def test_parseFileAndReport(self):
        """
        L{tree.parseFileAndReport} parses the contents of the filename passed
        to it and returns the corresponding DOM.
        """
        path = FilePath(self.mktemp())
        path.setContent('<foo bar="baz">hello</foo>\n')

        document = tree.parseFileAndReport(path.path)
        self.assertXMLEqual(
            document.toxml(),
            '<?xml version="1.0" ?><foo bar="baz">hello</foo>')


    def test_parseFileAndReportMismatchedTags(self):
        """
        If the contents of the file passed to L{tree.parseFileAndReport}
        contain a mismatched tag, L{process.ProcessingFailure} is raised
        indicating the location of the open and close tags which were
        mismatched.
        """
        path = FilePath(self.mktemp())
        path.setContent('  <foo>\n\n  </bar>')

        err = self.assertRaises(
            process.ProcessingFailure, tree.parseFileAndReport, path.path)
        self.assertEqual(
            str(err),
            "mismatched close tag at line 3, column 4; expected </foo> "
            "(from line 1, column 2)")

        # Test a case which requires involves proper close tag handling.
        path.setContent('<foo><bar></bar>\n  </baz>')

        err = self.assertRaises(
            process.ProcessingFailure, tree.parseFileAndReport, path.path)
        self.assertEqual(
            str(err),
            "mismatched close tag at line 2, column 4; expected </foo> "
            "(from line 1, column 0)")


    def test_parseFileAndReportParseError(self):
        """
        If the contents of the file passed to L{tree.parseFileAndReport} cannot
        be parsed for a reason other than mismatched tags,
        L{process.ProcessingFailure} is raised with a string describing the
        parse error.
        """
        path = FilePath(self.mktemp())
        path.setContent('\n   foo')

        err = self.assertRaises(
            process.ProcessingFailure, tree.parseFileAndReport, path.path)
        self.assertEqual(str(err), 'syntax error at line 2, column 3')


    def test_parseFileAndReportIOError(self):
        """
        If an L{IOError} is raised while reading from the file specified to
        L{tree.parseFileAndReport}, a L{process.ProcessingFailure} is raised
        indicating what the error was.  The file should be closed by the
        time the exception is raised to the caller.
        """
        class FakeFile:
            _open = True
            def read(self, bytes=None):
                raise IOError(errno.ENOTCONN, 'socket not connected')

            def close(self):
                self._open = False

        theFile = FakeFile()
        def fakeOpen(filename):
            return theFile

        err = self.assertRaises(
            process.ProcessingFailure, tree.parseFileAndReport, "foo", fakeOpen)
        self.assertEqual(str(err), "socket not connected, filename was 'foo'")
        self.assertFalse(theFile._open)



class XMLParsingTests(unittest.TestCase):
    """
    Tests for various aspects of parsing a Lore XML input document using
    L{tree.parseFileAndReport}.
    """
    def _parseTest(self, xml):
        path = FilePath(self.mktemp())
        path.setContent(xml)
        return tree.parseFileAndReport(path.path)


    def test_withoutDocType(self):
        """
        A Lore XML input document may omit a I{DOCTYPE} declaration.  If it
        does so, the XHTML1 Strict DTD is used.
        """
        # Parsing should succeed.
        document = self._parseTest("<foo>uses an xhtml entity: &copy;</foo>")
        # But even more than that, the &copy; entity should be turned into the
        # appropriate unicode codepoint.
        self.assertEqual(
            domhelpers.gatherTextNodes(document.documentElement),
            u"uses an xhtml entity: \N{COPYRIGHT SIGN}")


    def test_withTransitionalDocType(self):
        """
        A Lore XML input document may include a I{DOCTYPE} declaration
        referring to the XHTML1 Transitional DTD.
        """
        # Parsing should succeed.
        document = self._parseTest("""\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<foo>uses an xhtml entity: &copy;</foo>
""")
        # But even more than that, the &copy; entity should be turned into the
        # appropriate unicode codepoint.
        self.assertEqual(
            domhelpers.gatherTextNodes(document.documentElement),
            u"uses an xhtml entity: \N{COPYRIGHT SIGN}")


    def test_withStrictDocType(self):
        """
        A Lore XML input document may include a I{DOCTYPE} declaration
        referring to the XHTML1 Strict DTD.
        """
        # Parsing should succeed.
        document = self._parseTest("""\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<foo>uses an xhtml entity: &copy;</foo>
""")
        # But even more than that, the &copy; entity should be turned into the
        # appropriate unicode codepoint.
        self.assertEqual(
            domhelpers.gatherTextNodes(document.documentElement),
            u"uses an xhtml entity: \N{COPYRIGHT SIGN}")


    def test_withDisallowedDocType(self):
        """
        A Lore XML input document may not include a I{DOCTYPE} declaration
        referring to any DTD other than XHTML1 Transitional or XHTML1 Strict.
        """
        self.assertRaises(
            process.ProcessingFailure,
            self._parseTest,
            """\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-frameset.dtd">
<foo>uses an xhtml entity: &copy;</foo>
""")



class XMLSerializationTests(unittest.TestCase, _XMLAssertionMixin):
    """
    Tests for L{tree._writeDocument}.
    """
    def test_nonASCIIData(self):
        """
        A document which contains non-ascii characters is serialized to a
        file using UTF-8.
        """
        document = dom.Document()
        parent = dom.Element('foo')
        text = dom.Text()
        text.data = u'\N{SNOWMAN}'
        parent.appendChild(text)
        document.appendChild(parent)
        outFile = self.mktemp()
        tree._writeDocument(outFile, document)
        self.assertXMLEqual(
            FilePath(outFile).getContent(),
            u'<foo>\N{SNOWMAN}</foo>'.encode('utf-8'))



class LatexSpitterTestCase(unittest.TestCase):
    """
    Tests for the Latex output plugin.
    """
    def test_indexedSpan(self):
        """
        Test processing of a span tag with an index class results in a latex
        \\index directive the correct value.
        """
        doc = dom.parseString('<span class="index" value="name" />').documentElement
        out = StringIO()
        spitter = LatexSpitter(out.write)
        spitter.visitNode(doc)
        self.assertEqual(out.getvalue(), u'\\index{name}\n')



class ScriptTests(unittest.TestCase):
    """
    Tests for L{twisted.lore.scripts.lore}, the I{lore} command's
    implementation,
    """
    def test_getProcessor(self):
        """
        L{lore.getProcessor} loads the specified output plugin from the
        specified input plugin.
        """
        processor = lore.getProcessor("lore", "html", options)
        self.assertNotIdentical(processor, None)
