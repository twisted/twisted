# -*- test-case-name: twisted.lore -*-
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implementation of the primary Lore processor which deals with regular
documents.
"""

from os.path import splitext

from twisted.lore import tree, latex, lint, process
from twisted.lore.indexer import Indexer
from twisted.web import sux, microdom

htmlDefault = {'template': 'template.tpl', 'baseurl': '%s', 'ext': '.html'}


class HTMLGenerator(object):
    """
    Support generation of an HTML document.
    """
    def __init__(self, options, filenameGenerator):
        self._options = htmlDefault.copy()
        self._options.update(options)
        self._filenameGenerator = filenameGenerator


    def _getTemplateDocument(self, filename):
        try:
            fp = file(filename)
            return microdom.parse(fp)
        except IOError, e:
            raise process.NoProcessorError(e.filename+": "+e.strerror)
        except sux.ParseError, e:
            raise process.NoProcessorError(str(e))


    def generate(self, file, linkrel, book=None, indexer=None, toc=None, outputFilename=None):
        """
        Load and parse the Lore input document in the given file, transform it
        according to the given options, generate an output document, and write
        it to a file.

        @type filename: C{str}
        @param filename: The name of the file containing the input.

        @type linkrel: C{str}
        @param linkrel: An prefix to apply to all relative links in C{src} or
            C{href} attributes in the input document when generating the output
            document.

        @type book: L{Book}
        @param book: An object representing a larger document being generated.

        @type indexer: L{Indexer}
        @param indexer: An object representing an index for a larger document
            being generated.

        @type toc: L{TableOfContents}
        @param toc: An object representing the table of contents of a larger
            document being generated.

        @type outputFilename: C{str}
        @param outputFilename: If specified, the name of the file to which the
            output document will be written.

        @return: C{None}
        """
        if outputFilename is None:
            outputFilename = splitext(file)[0] + self._options['ext']
        templateDocument = self._getTemplateDocument(self._options['template'])
        return tree.doFile(
            file, linkrel, self._options['ext'], self._options['baseurl'],
            templateDocument, self._options, self._filenameGenerator,
            book, indexer, toc, outputFilename)


    def generateIndex(self, book, indexer, linkrel):
        """
        Output an index based on the given book and indexer objects.

        @type book: L{Book}
        @param book: An object representing a larger document being generated.

        @type indexer: L{Indexer}
        @param indexer: An object representing an index for a larger document
            being generated.

        @type linkrel: C{str}
        @param linkrel: An prefix to apply to all relative links in C{src} or
            C{href} attributes in the input document when generating the output
            document.

        @return: A DOM object which represents the index document.
        """
        template = self._getTemplateDocument(
            book.getIndexTemplateFilename() or self._options['template'])
        document = indexer.toDocument()
        discardIndexer = Indexer()
        discardIndexer.setIndexFilename(indexer.getIndexFilename())
        tree.doDocument(
            document, template, linkrel, None, None, self._options['ext'],
            self._options['baseurl'], self._options, self._filenameGenerator,
            None, discardIndexer, None, None)
        return template


    def setTitle(self, template, title, chapterNumber):
        """
        @see L{tree.setTitle}.
        """
        return tree.setTitle(template, title, chapterNumber)


    def setIndexLink(self, template, indexFilename):
        """
        @see L{tree.setIndexLink}.
        """
        return tree.setIndexLink(template, indexFilename)


    def __call__(self, *a, **kw):
        # XXX deprecate this
        return self.generate(*a, **kw)



class ProcessingFunctionFactory:
    """
    Trivial stateless class which can hand out generator objects for different
    formats.
    """
    def getGenerator(self, output, config):
        """
        Give back a callable which will return a generator for the specified
        output format.

        @type output: C{str}
        @param output: One of C{'html'}, C{'latex'}, or C{'lint'}.
        """
        try:
            return getattr(self, 'generate_' + output)
        except AttributeError:
            raise process.NoProcessorError("cannot generate " + output + " output")


    def getDoFile(self):
        return tree.doFile

    def generate_html(self, options, filenameGenerator=tree.getOutputFileName):
        """
        Return an HTML generator.
        """
        return HTMLGenerator(options, filenameGenerator)


    latexSpitters = {None: latex.LatexSpitter,
                     'section': latex.SectionLatexSpitter,
                     'chapter': latex.ChapterLatexSpitter,
                     'book': latex.BookLatexSpitter,
                     }

    def generate_latex(self, options, filenameGenerator=None):
        spitter = self.latexSpitters[None]
        for (key, value) in self.latexSpitters.items():
            if key and options.get(key):
               spitter = value
        df = lambda file, linkrel, book=None, indexer=None, toc=None: latex.convertFile(
            file, spitter)
        return df

    def getLintChecker(self):
        return lint.getDefaultChecker()

    def generate_lint(self, options, filenameGenerator=None):
        checker = self.getLintChecker()
        return lambda file, linkrel, book=None, indexer=None, toc=None: lint.doFile(file, checker)

factory = ProcessingFunctionFactory()
