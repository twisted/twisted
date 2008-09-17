# Copyright (c) 2008 Twisted Matrix Laboratories.
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

import os, shutil
from StringIO import StringIO

from twisted.trial import unittest

from twisted.lore import tree, process, indexer, numberer, htmlbook, default
from twisted.lore.default import factory
from twisted.lore.latex import LatexSpitter

from twisted.python.util import sibpath

from twisted.lore.scripts import lore

from twisted.web import microdom, domhelpers

def sp(originalFileName):
    return sibpath(__file__, originalFileName)

options = {"template" : sp("template.tpl"), 'baseurl': '%s', 'ext': '.xhtml' }
d = options

def filenameGenerator(originalFileName, outputExtension):
    return os.path.splitext(originalFileName)[0]+"1"+outputExtension

def filenameGenerator2(originalFileName, outputExtension):
    return os.path.splitext(originalFileName)[0]+"2"+outputExtension


class TestFactory(unittest.TestCase):

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
        self.assertEqualsString(expected, act)

    def assertEqualsString(self, expected, act):
        if len(expected) != len(act): print "Actual: " + act ##d
        self.assertEquals(len(expected), len(act))
        for i in range(len(expected)):
            e = expected[i]
            a = act[i]
            self.assertEquals(e, a, "differ at %d: %s vs. %s" % (i, e, a))
        self.assertEquals(expected, act)

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
        htmlGenerator = factory.generate_html(options)
        htmlGenerator(self.file, self.linkrel)
        self.assertEqualFiles('good_simple.xhtml', 'simple.xhtml')

    def testProcessingFunctionFactoryWithFilenameGenerator(self):
        htmlGenerator = factory.generate_html(options, filenameGenerator2)
        htmlGenerator(self.file, self.linkrel)
        self.assertEqualFiles('good_simple.xhtml', 'simple2.xhtml')

    def test_doFile(self):
        templ = microdom.parse(open(d['template']))

        tree.doFile(self.file, self.linkrel, d['ext'], d['baseurl'], templ, d)
        self.assertEqualFiles('good_simple.xhtml', 'simple.xhtml')

    def test_doFile_withFilenameGenerator(self):
        templ = microdom.parse(open(d['template']))

        tree.doFile(self.file, self.linkrel, d['ext'], d['baseurl'], templ, d, filenameGenerator)
        self.assertEqualFiles('good_simple.xhtml', 'simple1.xhtml')

    def test_munge(self):
        indexer.setIndexFilename("lore_index_file.html")
        doc = microdom.parse(open(self.file))
        templ = microdom.parse(open(d['template']))
        node = templ.cloneNode(1)
        tree.munge(doc, node, self.linkrel,
                   os.path.dirname(self.file),
                   self.file,
                   d['ext'], d['baseurl'], d)
        self.assertEqualsFile('good_internal.xhtml', node.toprettyxml())

    def test_getProcessor(self):
        options = { 'template': sp('template.tpl'), 'ext': '.xhtml', 'baseurl': 'burl',
                    'filenameMapping': None }
        p = process.getProcessor(default, "html", options)
        p(sp('simple3.html'), self.linkrel)
        self.assertEqualFiles('good_simple.xhtml', 'simple3.xhtml')

    def test_getProcessorWithFilenameGenerator(self):
        options = { 'template': sp('template.tpl'),
                    'ext': '.xhtml',
                    'baseurl': 'burl',
                    'filenameMapping': 'addFoo' }
        p = process.getProcessor(default, "html", options)
        p(sp('simple4.html'), self.linkrel)
        self.assertEqualFiles('good_simple.xhtml', 'simple4foo.xhtml')

    def test_outputdirGenerator(self):
        normp = os.path.normpath; join = os.path.join
        inputdir  = normp(join("/", 'home', 'joe'))
        outputdir = normp(join("/", 'away', 'joseph'))
        actual = process.outputdirGenerator(join("/", 'home', 'joe', "myfile.html"),
                                            '.xhtml', inputdir, outputdir)
        expected = normp(join("/", 'away', 'joseph', 'myfile.xhtml'))
        self.assertEquals(expected, actual)

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
        templ = microdom.parse(open(d['template']))
        tmp = self.makeTemp('lore_index_test.xhtml')

        tree.doFile(os.path.join(tmp, 'lore_index_test.xhtml'),
                    self.linkrel, '.html', d['baseurl'], templ, d)
        self.assertEqualFiles1("lore_index_test_out.html",
                               os.path.join(tmp, "lore_index_test.html"))

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
            self.assertEquals(dct[k], expected[k])

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
        self.assertEquals(None, result)
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
        self.assertEquals(None, result)
        self.assertEqualFiles1("lore_index_file_unnumbered_multiple_out.html", indexFilename + ".html")
        self.assertEqualFiles1("lore_index_test_out.html",
                               os.path.join(tmp, "lore_index_test.html"))
        self.assertEqualFiles1("lore_index_test_out2.html",
                               os.path.join(tmp, "lore_index_test2.html"))

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

        self.assertEquals(None, result)
        #self.assertEqualFiles1("lore_index_file_out_multiple.html", indexFilename + ".tns")
        #                       VVV change to new, numbered files
        self.assertEqualFiles("lore_numbering_test_out.html", "lore_numbering_test.tns")
        self.assertEqualFiles("lore_numbering_test_out2.html", "lore_numbering_test2.tns")


    def test_setIndexLink(self):
        """
        Tests to make sure that index links are processed when an index page
        exists and removed when there is not.
        """
        templ = microdom.parse(open(d['template']))
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

        self.assertEquals(
            [],
            domhelpers.findElementsWithAttribute(templ,
                                                 "class",
                                                 "index-link"))

        indexLinks = domhelpers.findElementsWithAttribute(templ,
                                                          "href",
                                                          indexFilename)
        self.assertTrue(len(indexLinks) >= numLinks)

        templ = microdom.parse(open(d['template']))
        self.assertNotEquals(
            [],
            domhelpers.findElementsWithAttribute(templ,
                                                 "class",
                                                 "index-link"))
        indexFilename = None

        tree.setIndexLink(templ, indexFilename)

        self.assertEquals(
            [],
            domhelpers.findElementsWithAttribute(templ,
                                                 "class",
                                                 "index-link"))




class LatexSpitterTestCase(unittest.TestCase):
    """
    Tests for the Latex output plugin.
    """
    def test_indexedSpan(self):
        """
        Test processing of a span tag with an index class results in a latex
        \\index directive the correct value.
        """
        dom = microdom.parseString('<span class="index" value="name" />').documentElement
        out = StringIO()
        spitter = LatexSpitter(out.write)
        spitter.visitNode(dom)
        self.assertEqual(out.getvalue(), u'\\index{name}\n')
