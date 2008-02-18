# -*- test-case-name: twisted.lore.test.test_lore -*-
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Another ad hoc collection of apparently random Lore functionality.  See class
and function docstrings for details.
"""

import sys
import os


class NoProcessorError(Exception):
    pass


class ProcessingFailure(Exception):
    pass


cols = 79


def dircount(d):
    return len([1 for el in d.split("/") if el != '.'])


class Walker:
    """
    A visitor which runs lore input documents in a directory hierarchy through
    the various transformations defined by lore and produces output files
    alongside them.

    @ivar generator: A generator, such as L{HTMLGenerator} which will be used
        to produce output documents from the input documents.

    @type linkrel: C{str}
    @param linkrel: An prefix to apply to all relative links in C{src} or
        C{href} attributes in the input document when generating the output
        document.

    @type fext: C{str}
    @ivar fext: The file extension which will be used to identify input files.

    @ivar walked: A C{list} of two-tuples, the first element of each tuple is a
        C{str} giving the I{linkrel} value to use when processing the input
        document which is given by the second element of each tuple.

    @ivar failures: A C{list} of two-tuples.  The first element of each tuple
        is a C{str} giving the name of an input file for which there was an
        exception during processing.  The second element of each tuple is the
        exception which occurred.

    @ivar templateFilename: The name of the template to use when producing
        output documents.
    """
    def __init__(self, generator, fext, linkrel, templateFilename='template.tpl'):
        self.generator = generator
        self.linkrel = linkrel
        self.fext = fext
        self.walked = []
        self.failures = []
        self.templateFilename = templateFilename

    def walkdir(self, topdir, prefix=''):
        """
        Find all of the input documents in the given directory and record them
        in C{self.walked}.
        """
        self.basecount = dircount(topdir)
        os.path.walk(topdir, self.walk, prefix)


    def walk(self, prefix, d, names):
        """
        Visitor function used by L{walkdir}.
        """
        linkrel = prefix + '../' * (dircount(d) - self.basecount)
        for name in names:
            fullpath = os.path.join(d, name)
            fext = os.path.splitext(name)[1]
            if fext == self.fext:
                self.walked.append((linkrel, fullpath))


    def generate(self, book=None, indexer=None, toc=None, numberer=None):
        """
        Process all of the input documents previously discovered by L{walkdir}.

        @type book: L{Book}
        @param book: An object representing the document collection being
            generated.

        @type indexer: L{Indexer}
        @param indexer: An object representing an index for a larger document
            being generated.

        @type toc: L{TableOfContents}
        @param toc: An object representing the table of contents of a larger
            document being generated.
        """
        i = 0

        indexer.clearEntries()

        for linkrel, fullpath in self.walked:
            linkrel = self.linkrel + linkrel
            i += 1
            fname = os.path.splitext(fullpath)[0]
            self.percentdone((float(i) / len(self.walked)), fname)
            try:
                self.generator.generate(fullpath, linkrel, book, indexer, toc, numberer)
            except ProcessingFailure, e:
                self.failures.append((fullpath, e))
        if book is not None:
            self._writeIndex(book, indexer, linkrel)
            self._writeTOC(toc, indexer.getIndexFilename())
        self.percentdone(1., None)


    def _writeIndex(self, book, indexer, linkrel):
        """
        Generate the index output document.  Return a list of errors which
        occurred while doing so.
        """
        try:
            output = self.generator.generateIndex(book, indexer, linkrel)
        except ProcessingFailure, e:
            return [(indexFilename, e)]
        else:
            file(indexer.getIndexFilename(), 'w').write(output.toprettyxml(addindent='  '))
            return []


    def _writeTOC(self, toc, indexFilename):
        """
        Generate the table of contents document.
        """
        toc.generateTableOfContents(
            self.generator.setTitle, self.generator.setIndexLink,
            indexFilename, self.templateFilename)


    def percentdone(self, percent, fname):
        """
        Report overall progress.
        """
        # override for neater progress bars
        proglen = 40
        hashes = int(percent * proglen)
        spaces = proglen - hashes
        progstat = "[%s%s] (%s)" %('#' * hashes, ' ' * spaces,fname or "*Done*")
        progstat += (cols - len(progstat)) * ' '
        progstat += '\r'
        sys.stdout.write(progstat)
        sys.stdout.flush()
        if fname is None:
            print



class PlainReportingWalker(Walker):
    def percentdone(self, percent, fname):
        if fname:
            print fname



class NullReportingWalker(Walker):
    def percentdone(self, percent, fname):
        pass



def parallelGenerator(originalFileName, outputExtension):
    return os.path.splitext(originalFileName)[0] + outputExtension


def fooAddingGenerator(originalFileName, outputExtension):
    return os.path.splitext(originalFileName)[0] + "foo" + outputExtension


def outputdirGenerator(originalFileName, outputExtension, inputdir, outputdir):
    originalFileName = os.path.abspath(originalFileName)
    abs_inputdir = os.path.abspath(inputdir)
    if os.path.commonprefix((originalFileName, abs_inputdir)) != abs_inputdir:
        raise ValueError("Original file name '" + originalFileName +
              "' not under input directory '" + abs_inputdir + "'")

    adjustedPath = os.path.join(outputdir, os.path.basename(originalFileName))

    # XXX
    from twisted.lore import tree
    return tree.getOutputFileName(adjustedPath, outputExtension)


def getFilenameGenerator(config, outputExt):
    if config.get('outputdir'):
        return (lambda originalFileName, outputExtension:
            outputdirGenerator(originalFileName, outputExtension,
                               os.path.abspath(config.get('inputdir')),
                               os.path.abspath(config.get('outputdir'))))
    else:
        # XXX
        from twisted.lore import tree
        return tree.getOutputFileName


def getProcessor(module, output, config):
    return getOutputGenerator(module, output, config).generate


def getOutputGenerator(module, output, config):
    """
    Return an object which can create an output document in the given format.
    """
    if config.get('ext'):
        ext = config['ext']
    else:
        from default import htmlDefault
        ext = htmlDefault['ext']

    return module.factory.getGenerator(output, config)(
        config, getFilenameGenerator(config, ext))
