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
# __ hierarchical index entries
# 
# ++ add parameter for what the index filename should be
# __ add ability to NOT index (maybe if index not specified?)
# 
# ++ put actual index filename into INDEX link (if any) in the template
# 
# __ make index look nice
# __ make text of index entry links be section numbers
# 
# __ put all of our test files someplace neat and tidy
# 
from twisted.trial import unittest

from twisted.lore.default import *
from twisted.lore import tree
from twisted.lore import process
from twisted.lore import indexer
from twisted.lore import default

from twisted.python.util import sibpath
from twisted.python import usage

from twisted.scripts import lore

import os

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

    def setUp(self):
        indexer.setIndexFilename()
        indexer.clearEntries()

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
        inputdir  = os.path.normpath(os.path.join("/", 'home', 'joe'))
        outputdir = os.path.normpath(os.path.join("/", 'away', 'joseph'))
        actual = process.outputdirGenerator(os.path.join("/", 'home', 'joe', "myfile.html"), '.xhtml',
                                            inputdir, outputdir)
        self.assertEquals(os.path.join("/", 'away', 'joseph', 'myfile.xhtml'), actual)
        
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

        tree.doFile(sp('lore_index_test.xhtml'), self.linkrel, '.html', d['baseurl'], templ, d)
        self.assertEqualFiles("lore_index_test_out.html", "lore_index_test.html")

    def test_indexEntriesAdded(self):
        indexer.addEntry('lore_index_test.html', 'index02', 'language of programming')
        indexer.addEntry('lore_index_test.html', 'index01', 'programming language')
        indexer.setIndexFilename("lore_index_file.html")
        indexer.generateIndex()
        self.assertEqualFiles1("lore_index_file_out.html", "lore_index_file.html")

    def test_runningLore(self):
        options = lore.Options()
        templateFilename = sp('template.tpl')
        inputFilename = sp('lore_index_test.xhtml')
        indexFilename = 'theIndexFile'
        options.parseOptions(['--null', '--config', 'template=%s' % templateFilename,
                              '--index=%s' % indexFilename,
                              inputFilename])
        result = lore.runGivenOptions(options)
        self.assertEquals(None, result)
        self.assertEqualFiles1("lore_index_file_out.html", indexFilename + ".html")

    def test_runningLoreMultipleFiles(self):
        options = lore.Options()
        templateFilename = sp('template.tpl')
        inputFilename = sp('lore_index_test.xhtml')
        inputFilename2 = sp('lore_index_test2.xhtml')
        indexFilename = 'theIndexFile'
        options.parseOptions(['--null', '--config', 'template=%s' % templateFilename,
                              '--index=%s' % indexFilename,
                              inputFilename, inputFilename2])
        result = lore.runGivenOptions(options)
        self.assertEquals(None, result)
        self.assertEqualFiles1("lore_index_file_out_multiple.html", indexFilename + ".html")
        self.assertEqualFiles("lore_index_test_out.html", "lore_index_test.html")
        self.assertEqualFiles("lore_index_test_out2.html", "lore_index_test2.html")

    def test_NumberedSections(self):
        # run two files through lore, with numbering turned on
        # every h2 should be numbered:
        # first  file's h2s should be 1.1, 1.2
        # second file's h2s should be 2.1, 2.2
        templateFilename = sp('template.tpl')
        inputFilename = sp('lore_index_test.xhtml')
        inputFilename2 = sp('lore_index_test2.xhtml')
        indexFilename = 'theIndexFile'
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
        self.assertEqualFiles("lore_index_test_out.html", "lore_index_test.tns")
        self.assertEqualFiles("lore_index_test_out2.html", "lore_index_test2.tns")

########################################

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

