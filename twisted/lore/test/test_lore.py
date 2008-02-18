# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

# IMPORTANT:
# When all the unit tests for Lore run, there's one more test to do:
#   from a shell,
#   cd Twisted/
#   admin/process-docs
# It takes a while to run (2:03 on a reasonable box)
# Make sure there are no errors!  Warnings are OK.

# To run from trunk (i.e. Twisted/):
# $ trial twisted.lore                      # whole Lore test suite
# $ trial twisted.lore.test_lore            # Just this file
# $ trial twisted.lore.test_lore.TestFactory                 # Just one class in this file
# $ trial twisted.lore.test.test_lore.TestFactory.test_book  # Just one method in this file

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
from os.path import join

from StringIO import StringIO

from twisted.trial import unittest

from twisted.lore import tree, process, htmlbook, default
from twisted.lore.default import factory
from twisted.lore.latex import LatexSpitter
from twisted.lore.indexer import Indexer, _stripTag, sortingKeyed, getTemplateFilenameOrDefault
from twisted.lore.indexer import TocEntry, TableOfContents

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


DONTCARE = object()


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


    def assertEqualsString(self, expected, actual):
        for i in range(min(len(expected), len(actual))):
            e = expected[i]
            a = actual[i]
            self.assertEquals(
                e, a,
                "differ at %d: expected %s vs. actual %s" % (
                    i,
                    (expected[i - 40:i], expected[i:i + 40]),
                    (actual[i - 40:i], actual[i:i + 40])))
        self.assertEquals(expected, actual)


    def makeTemp(self, *filenames):
        tmp = self.mktemp()
        os.mkdir(tmp)
        for filename in filenames:
            tmpFile = join(tmp, filename)
            shutil.copyfile(sp(filename), tmpFile)
        return tmp


    def assertIsTextNode(self, node, contents=None, parent=DONTCARE):
        """
        Check that C{node} is an instance of C{microdom.Text} and
        that its contents are C{contents}.
        If C{parent} is given, check that C{node}'s parent is C{parent}.
        """
        self.assertTrue(isinstance(node, microdom.Text))
        if contents:
            self.assertEquals(contents, node.nodeValue)
        # Sentinel value, since we might want to check for None
        if parent is not DONTCARE:
            self.assertEquals(parent, node.parentNode)


    def test_processingFunctionFactory(self):
        htmlGenerator = factory.generate_html(options)
        htmlGenerator(self.file, self.linkrel)
        self.assertEqualFiles('good_simple.xhtml', 'simple.xhtml')


    def test_processingFunctionFactoryWithFilenameGenerator(self):
        htmlGenerator = factory.generate_html(options, filenameGenerator2)
        htmlGenerator(self.file, self.linkrel)
        self.assertEqualFiles('good_simple.xhtml', 'simple2.xhtml')


    def test_doFile(self):
        templ = microdom.parse(open(d['template']))

        tree.doFile(self.file, self.linkrel, d['ext'], d['baseurl'], templ, d)
        self.assertEqualFiles('good_simple.xhtml', 'simple.xhtml')


    def test_doFile_withFilenameGenerator(self):
        templ = microdom.parse(open(d['template']))

        tree.doFile(self.file, self.linkrel, d['ext'], d['baseurl'],
                    templ, d, filenameGenerator)
        self.assertEqualFiles('good_simple.xhtml', 'simple1.xhtml')


    def test_munge(self):
        indexer = Indexer()
        indexer.setIndexFilename("lore_index_file.html")
        doc = microdom.parse(open(self.file))
        templ = microdom.parse(open(d['template']))
        node = templ.cloneNode(1)
        tree.munge(doc, node, self.linkrel,
                   os.path.dirname(self.file),
                   self.file,
                   d['ext'], d['baseurl'], d,
                   indexer=indexer)
        self.assertEqualsFile('good_internal.xhtml', node.toprettyxml())


    def test_getProcessor(self):
        options = {'template': sp('template.tpl'), 'ext': '.xhtml',
                   'baseurl': 'burl', 'filenameMapping': None }
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
        normp = os.path.normpath
        inputdir  = normp(join("/", 'home', 'joe'))
        outputdir = normp(join("/", 'away', 'joseph'))
        actual = process.outputdirGenerator(
            join("/", 'home', 'joe', "myfile.html"),
            '.xhtml', inputdir, outputdir)
        expected = normp(join("/", 'away', 'joseph', 'myfile.xhtml'))
        self.assertEquals(expected, actual)


    def test_outputdirGeneratorBadInput(self):
        options = {'outputdir': '/away/joseph/', 'inputdir': '/home/joe/' }
        self.assertRaises(ValueError, process.outputdirGenerator,
                          '.html', '.xhtml', **options)


    def test_makeSureDirectoryExists(self):
        dirname = join("tmp", 'nonexistentdir')
        if os.path.exists(dirname):
            os.rmdir(dirname)
        self.failIf(os.path.exists(dirname))
        filename = join(dirname, 'newfile')
        tree.makeSureDirectoryExists(filename)
        self.failUnless(os.path.exists(dirname), 'should have created dir')
        os.rmdir(dirname)


    def test_stripTag(self):
        """
        _stripTag() should leave text with no tags alone, leave text with tags
        but not the specified tag alone, and remove all instances (open and
        close) of the specified tag from text that contains it.
        """
        self.assertEquals('No tag in this text',
            _stripTag('em', 'No tag in this text'))
        self.assertEquals('Wrong <strong>tag</strong> in this text',
            _stripTag('em', 'Wrong <strong>tag</strong> in this text'))
        self.assertEquals('Right tag in this text',
            _stripTag('em', 'Right <em>tag</em> in this text'))
        self.assertEquals('Right tag in this text',
            _stripTag('em', 'Right <em>tag</em> in <em>this</em> text'))


    def test_sortingKeyed(self):
        """
        sortingKeyed() should construct the sort key as lowercased text, with
        any <em> tag at the beginning removed, along with its closing tag.
        It should then return a pair of the sort key and the original text.
        """
        self.assertEquals(('regular text', 'regular text'),
            sortingKeyed('regular text'))
        self.assertEquals(('capitalized text', 'Capitalized Text'),
            sortingKeyed('Capitalized Text'))
        self.assertEquals(('capitalized text', 'CAPITALIZED TEXT'),
            sortingKeyed('CAPITALIZED TEXT'))
        self.assertEquals(('emphasized', '<em>emphasized</em>'),
            sortingKeyed('<em>emphasized</em>'))
        self.assertEquals(
            ('beginning emphasized', '<em>Beginning</em> emphasized'),
            sortingKeyed('<em>Beginning</em> emphasized'))
        self.assertEquals(
            ('beginning emphasized end',
             '<em>Beginning</em> emphasized <em>end</em>'),
            sortingKeyed('<em>Beginning</em> emphasized <em>end</em>'))
        self.assertEquals(
            ('some <em>emphasized</em>, some <em>not</em>',
             'Some <em>emphasized</em>, some <em>not</em>'),
            sortingKeyed('Some <em>emphasized</em>, some <em>not</em>'))


    def test_getTemplateFilenameOrDefault(self):
        """
        getTemplateFilenameOrDefault() should return the given filename,
        or if None is given, return the default filename.
        """
        default = 'template.tpl'
        given = 'givenfilename.tpl'
        self.assertEquals(given, getTemplateFilenameOrDefault(given))
        self.assertEquals(default, getTemplateFilenameOrDefault(None))
        self.assertEquals(default,
                          getTemplateFilenameOrDefault(default))


    def test_indexAnchorsAdded(self):
        indexer = Indexer()
        indexer.setIndexFilename('theIndexFile.html')
        # generate the output file
        templ = microdom.parse(open(d['template']))
        tmp = self.makeTemp('lore_index_test.xhtml')

        tree.doFile(join(tmp, 'lore_index_test.xhtml'),
                    self.linkrel, '.html', d['baseurl'], templ, d,
                    indexer=indexer)
        self.assertEqualFiles1("lore_index_test_out.html",
                               join(tmp, "lore_index_test.html"))


    def assertIsIndexHeader(self, node, letter):
        """
        Check that C{node} is an instance of C{microdom.Element} that is
        an C{H2} header, and that it has one child node which is a Text
        node containing only C{letter}.
        """
        self.assertTrue(isinstance(node, microdom.Element))
        self.assertEquals('h2', node.nodeName)
        self.assertEquals(1, len(node.childNodes))
        self.assertIsTextNode(node.childNodes[0], letter, node)


    def assertIsIndexEntry(self, nodes, text, faslist, optanch=None,
                           optsec=None):
        """
        Check that C{nodes} is a list of nodes constituting an index entry
        with files, anchors, and sections as listed in the list of tuples
        C{faslist}. If only one file/anchor/section tuple is needed, it can be
        passed as individual arguments for convenience.
        """
        if not isinstance(faslist, (list, tuple)):
            faslist = [(faslist, optanch, optsec)]
        self.assertEquals(1 + 2*len(faslist), len(nodes))
        self.assertIsTextNode(nodes[0], '\n'+text+': ')

        i = 1
        for fas in faslist:
            filename, anchorname, section = fas
            n1 = nodes[i]
            self.assertEquals('a', n1.nodeName)
            self.assertEquals('%s#%s' % (filename, anchorname),
                              n1.getAttribute('href'))
            self.assertEquals(1, len(n1.childNodes))
            self.assertIsTextNode(n1.childNodes[0], section, n1)
            i += 2

        self.assertEquals('br', nodes[i-1].nodeName)


    def test_indexEntryGeneration(self):
        """
        generateIndexEntry() should generate an index entry.  Correctly.
        """
        indexer = Indexer()
        text = 'text of entry'
        filename = 'filename.html'
        anchorname = 'anchorname'
        section = '3.14'

        indexer.addEntry(filename, anchorname, text, section)
        nodes = indexer.generateIndexEntry(text)

        self.assertIsIndexEntry(nodes, text, filename, anchorname, section)


    def test_indexEntryGenerationManyRefs(self):
        """
        generateIndexEntry() should generate an index entry with multiple
        occurrences in the text.  Correctly.
        """
        indexer = Indexer()
        text = 'text of entry'
        filenames = ['filename.html', 'filename2.html', 'filename3.html']
        anchornames = ['anchorname', 'anchorname2', 'anchorname3']
        sections = ['3.14', '1.41', '10.2']

        for i in range(len(filenames)):
            indexer.addEntry(filenames[i], anchornames[i], text, sections[i])
        nodes = indexer.generateIndexEntry(text)

        self.assertIsIndexEntry(nodes, text,
            zip(filenames, anchornames, sections))


    def test_indexEntryGenerationSymbol(self):
        """
        generateIndexEntry(), when given text that begins with a
        non-alphanumeric character, should generate an index entry.  Correctly.
        """
        indexer = Indexer()
        text = '&-escaping'
        filenames = ['filename.html', 'filename2.html', 'filename3.html']
        anchornames = ['anchorname', 'anchorname2', 'anchorname3']
        sections = ['3.14', '1.41', '10.2']

        for i in range(len(filenames)):
            indexer.addEntry(filenames[i], anchornames[i], text, sections[i])
        nodes = indexer.generateIndexEntry(text)

        self.assertIsIndexEntry(nodes, text,
            zip(filenames, anchornames, sections))


    def test_indexEntryGenerationEmphasis(self):
        """
        generateIndexEntry(), when given text that contains an <em> tag,
        should generate an index entry.  Correctly.
        """
        indexer = Indexer()
        text = 'The <em>Kobayashi Maru</em>'
        filenames = ['filename.html']
        anchornames = ['anchorname']
        sections = ['9.89']
        filename, anchorname, section = filenames[0], anchornames[0], sections[0]

        for i in range(len(filenames)):
            indexer.addEntry(filenames[i], anchornames[i], text, sections[i])
        nodes = indexer.generateIndexEntry(text)

        self.assertEquals(1 + 2*len(filenames), len(nodes))
        n0 = nodes[0]
        self.assertEquals('span', n0.nodeName)
        self.assertEquals(3, len(n0.childNodes))
        self.assertIsTextNode(n0.childNodes[0], 'The ', n0)
        n0c1 = n0.childNodes[1]
        self.assertEquals('em', n0c1.nodeName)
        self.assertEquals(1, len(n0c1.childNodes))
        self.assertIsTextNode(n0c1.childNodes[0], 'Kobayashi Maru', n0c1)
        self.assertIsTextNode(n0.childNodes[-1], ': ', n0)

        n1 = nodes[1]
        self.assertEquals('a', n1.nodeName)
        self.assertEquals('%s#%s' % (filename, anchorname),
                          n1.getAttribute('href'))
        self.assertEquals(1, len(n1.childNodes))
        self.assertIsTextNode(n1.childNodes[0], section, n1)

        self.assertEquals('br', nodes[2].nodeName)


    def testIndexGenerationSkipped(self):
        """
        generateIndex(), when the index fiename is None,
        should skip generating an index and return "SKIPPED".
        """
        indexer = Indexer()
        indexer.setIndexFilename(None)
        result = indexer.generateIndex(None)
        self.assertEquals('SKIPPED', result)


    def test_indexGeneration(self):
        """
        generateIndexBody() should generate a DIV with class=body, containing
        H2 tags for each initial letter (preceded by a special one for Symbols),
        under which index entries are grouped.
        """
        indexer = Indexer()
        indexer.addEntry('lore_index_test.html', 'index02',
                         'language of programming', '1.3')
        indexer.addEntry('lore_index_test.html', 'index01',
                         'programming language', '1.2')
        indexer.addEntry('lore_index_test.html', 'index03',
                         '$ notation', '1.7')
        indexer.setIndexFilename("lore_index_file.html")

        body = indexer.generateIndexBody()

        self.assertEquals('div', body.nodeName)
        self.assertEquals('body', body.getAttribute('class'))

        children = body.childNodes
        self.assertEquals(12, len(children))
        self.assertIsIndexHeader(children[0], 'Symbols')
        self.assertIsIndexEntry(children[1:4], '$ notation',
            'lore_index_test.html', 'index03', '1.7')
        self.assertIsIndexHeader(children[4], 'L')
        self.assertIsIndexEntry(children[5:8], 'language of programming',
            'lore_index_test.html', 'index02', '1.3')
        self.assertIsIndexHeader(children[8], 'P')
        self.assertIsIndexEntry(children[9:12], 'programming language',
            'lore_index_test.html', 'index01', '1.2')


    def test_book(self):
        tmp = self.makeTemp()
        inputFilename = sp('lore_index_test.xhtml')

        bookFilename = join(tmp, 'lore_test_book.book')
        bf = open(bookFilename, 'w')
        bf.write('chapter(r"%s", None)\r\n' % inputFilename)
        bf.close()

        book = htmlbook.Book(bookFilename)
        expected = {'indexFilename': None,
                    'chapters': [(inputFilename, None)],
                    }
        dct = book.__dict__
        for k in dct:
            if k != 'filename':
                self.assertEquals(dct[k], expected[k])


    def test_runningLore(self):
        options = lore.Options()
        tmp = self.makeTemp('lore_index_test.xhtml')

        templateFilename = sp('template.tpl')
        indexTemplateFilename = sp('index-template.tpl')
        inputFilename = join(tmp, 'lore_index_test.xhtml')
        indexFilename = join(tmp, 'theIndexFile')

        bookFilename = join(tmp, 'lore_test_book.book')
        bf = open(bookFilename, 'w')
        bf.write('setIndexTemplateFilename(r"%s")\n' % indexTemplateFilename)
        bf.write('chapter(r"%s", None)\n' % inputFilename)
        bf.close()

        options.parseOptions(['--null', '--book=%s' % bookFilename,
                              '--config', 'template=%s' % templateFilename,
                              '--index=%s' % indexFilename
                              ])
        result = lore.runGivenOptions(options)
        self.assertEquals(None, result)

        # Rewrite the href attributes to include the full path to the target
        # output document.
        expected = file(sp("lore_index_file_unnumbered_out.html")).read()
        for i in range(1, 3):
            suffix = '#index%02d' % (i,)
            expected = expected.replace(
                'lore_index_test.html' + suffix,
                inputFilename.replace('.xhtml', '.html') + suffix)
        expected = expected.replace('index.html', indexFilename + '.html')
        self.assertEqualsString(
            expected.strip(),
            file(indexFilename + ".html").read().strip())



    def test_runningLoreMultipleFiles(self):
        tmp = self.makeTemp('lore_index_test.xhtml', 'lore_index_test2.xhtml')
        templateFilename = sp('template.tpl')
        indexTemplateFilename = sp('index-template.tpl')
        inputFilename = join(tmp, 'lore_index_test.xhtml')
        inputFilename2 = join(tmp, 'lore_index_test2.xhtml')
        indexFilename = join(tmp, 'theIndexFile')

        bookFilename = join(tmp, 'lore_test_book.book')
        bf = open(bookFilename, 'w')
        bf.write('setIndexTemplateFilename(r"%s")\n' % indexTemplateFilename)
        bf.write('chapter(r"%s", None)\n' % inputFilename)
        bf.write('chapter(r"%s", None)\n' % inputFilename2)
        bf.close()

        options = lore.Options()
        options.parseOptions(['--null', '--book=%s' % bookFilename,
                              '--config', 'template=%s' % templateFilename,
                              '--index=%s' % indexFilename
                              ])
        result = lore.runGivenOptions(options)
        self.assertEquals(None, result)

        # Rewrite the href attributes to include the full path to the target
        # output document.
        expected = file(sp("lore_index_file_unnumbered_multiple_out.html")).read()
        for i in range(1, 4):
            suffix = '#index%02d' % (i,)
            expected = expected.replace(
                'lore_index_test2.html' + suffix,
                inputFilename2.replace('.xhtml', '.html') + suffix)
            expected = expected.replace(
                'lore_index_test.html' + suffix,
                inputFilename.replace('.xhtml', '.html') + suffix)
        expected = expected.replace('index.html', indexFilename + '.html')
        self.assertEqualsString(
            expected.strip(),
            file(indexFilename + ".html").read().strip())

        expected = file(sp("lore_index_test_out.html")).read()
        expected = expected.replace("theIndexFile.html", indexFilename + ".html")
        self.assertEqualsString(
            expected,
            file(join(tmp, "lore_index_test.html")).read())

        expected = file(sp("lore_index_test_out2.html")).read()
        expected = expected.replace("theIndexFile.html", indexFilename + ".html")
        self.assertEqualsString(
            expected,
            file(join(tmp, "lore_index_test2.html")).read())


    def test_numberedSections(self):
        """
        When Lore is run with --number specified, the first file\'s numbered
        headings will all start with "1.", and the second file\'s will all
        start with "2.".
        """
        # run two files through lore, with numbering turned on
        # every h2 should be numbered:
        # first  file's h2s should be 1.1, 1.2
        # second file's h2s should be 2.1, 2.2
        indexFilename = 'theIndexFile'
        templateFilename = 'template.tpl'
        inputFilename = 'lore_numbering_test.xhtml'
        inputFilename2 = 'lore_numbering_test2.xhtml'
        tmp = self.makeTemp(templateFilename, inputFilename, inputFilename2)

        bookFilename = 'numberedsections.book'
        bf = open(join(tmp, bookFilename), 'w')
        bf.write('chapter(r"%s", 1)\n' % inputFilename)
        bf.write('chapter(r"%s", 2)\n' % inputFilename2)
        bf.close()

        oldwd = os.getcwd()
        os.chdir(tmp)
        options = lore.Options()
        options.parseOptions(['--null',
                              '--index=%s' % indexFilename,
                              '--book=%s' % bookFilename,
                              '--config', 'template=%s' % templateFilename,
                              '--config', 'ext=%s' % ".tns",
                              '--number',
                              ])
        result = lore.runGivenOptions(options)
        os.chdir(oldwd)

        self.assertEquals(None, result)
        self.assertEqualFiles1("lore_numbering_test_out.html",
            join(tmp, "lore_numbering_test.tns"))
        self.assertEqualFiles1("lore_numbering_test_out2.html",
            join(tmp, "lore_numbering_test2.tns"))


    def test_sections_not_numbered(self):
        """
        When Lore is run with --number specified, but with no book file,
        neither file\'s headings are numbererd.
        """
        # Run two files through lore, with numbering turned on, but no book file
        templateFilename = 'template.tpl'
        # Instead, copy these files to temp dir
        inputFilename = 'lore_numbering_test.xhtml'
        inputFilename2 = 'lore_numbering_test2.xhtml'
        tmp = self.makeTemp(templateFilename, inputFilename, inputFilename2)
        indexFilename = 'theIndexFile'

        # you can't number without a book:
        options = lore.Options()
        options.parseOptions(['--null',
                              '--index=%s' % indexFilename,
                              '--config',
                              'template=%s' % join(tmp, templateFilename),
                              '--config', 'ext=%s' % ".tns",
                              '--number',
                              join(tmp, inputFilename),
                              join(tmp, inputFilename2)])
        result = lore.runGivenOptions(options)

        self.assertEquals(None, result)
        self.assertEqualFiles1("sections_not_numbered_out.html",
            join(tmp, "lore_numbering_test.tns"))
        self.assertEqualFiles1("sections_not_numbered_out2.html",
            join(tmp, "lore_numbering_test2.tns"))


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
        root = microdom.parseString('<span class="index" value="name" />')
        dom = root.documentElement
        out = StringIO()
        spitter = LatexSpitter(out.write)
        spitter.visitNode(dom)
        self.assertEqual(out.getvalue(), u'\\index{name}\n')



class TableOfContentsTests(unittest.TestCase):
    """
    Tests for L{TableOfContents}.
    """
    def test_emptyCreation(self):
        """
        L{TableOfContents} should have an empty C{toc} list immediately after
        instantiation.
        """
        contents = TableOfContents()
        self.assertEqual(contents.toc, [])


    def test_addChapterTableOfContents(self):
        """
        L{TableOfContents.addChapterTableOfContents} should create a new
        L{TocEntry} and append it to the C{toc} list.
        """
        tree = object()
        title = object()
        outfile = object()
        reference = object()
        contents = TableOfContents()
        contents.addChapterTableOfContents(tree, title, outfile, reference)
        self.assertEqual(len(contents.toc), 1)
        self.assertTrue(isinstance(contents.toc[0], TocEntry))
        self.assertIdentical(contents.toc[0].tree, tree)
        self.assertIdentical(contents.toc[0].title, title)
        self.assertIdentical(contents.toc[0].outfile, outfile)
        self.assertIdentical(contents.toc[0].reference, reference)


    def test_clearTableOfContents(self):
        """
        L{TableOfContents.clearTableOfContents} should empty the C{toc} list.
        """
        contents = TableOfContents()
        contents.addChapterTableOfContents(None, None, None, None)
        contents.clearTableOfContents()
        self.assertEqual(contents.toc, [])


    def test_toDocument(self):
        """
        L{TableOfContents.toDocument} should return a copy of
        L{TableOfContents._baseDocument} with content appended to the body
        node.
        """
        tree = microdom.Element('div')
        tree.setAttribute('chapter', 'content')
        title = u'toDocument test'
        outfile = u'some filename'
        reference = u"6"
        contents = TableOfContents()
        contents._baseDocument = microdom.Document()
        contents._baseDocument.appendChild(
            contents._baseDocument.createElement('body'))
        contents.addChapterTableOfContents(tree, title, outfile, reference)
        result = contents.toDocument()
        [body] = domhelpers.findElementsWithAttribute(result, 'class', 'body')
        (heading, content) = body.childNodes
        self.assertEqual(heading.tagName, 'span')
        self.assertEqual(heading.childNodes[0].nodeValue, reference)
        self.assertEqual(heading.childNodes[1].tagName, 'a')
        self.assertEqual(heading.childNodes[1].getAttribute('href'), outfile)
        self.assertIdentical(content, tree)
