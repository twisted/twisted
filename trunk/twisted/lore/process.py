# -*- test-case-name: twisted.lore.test.test_lore -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

#
import sys, os
import tree #todo: get rid of this later
import indexer

class NoProcessorError(Exception):
    pass

class ProcessingFailure(Exception):
    pass

cols = 79

def dircount(d):
    return len([1 for el in d.split("/") if el != '.'])


class Walker:

    def __init__(self, df, fext, linkrel):
        self.df = df
        self.linkrel = linkrel
        self.fext = fext
        self.walked = []
        self.failures = []

    def walkdir(self, topdir, prefix=''):
        self.basecount = dircount(topdir)
        os.path.walk(topdir, self.walk, prefix)

    def walk(self, prefix, d, names):
        linkrel = prefix + '../' * (dircount(d) - self.basecount)
        for name in names:
            fullpath = os.path.join(d, name)
            fext = os.path.splitext(name)[1]
            if fext == self.fext:
                self.walked.append((linkrel, fullpath))
                
    def generate(self):
        i = 0
        indexer.clearEntries()
        tree.filenum = 0
        for linkrel, fullpath in self.walked:
            linkrel = self.linkrel + linkrel
            i += 1
            fname = os.path.splitext(fullpath)[0]
            self.percentdone((float(i) / len(self.walked)), fname)
            try:
                self.df(fullpath, linkrel)
            except ProcessingFailure, e:
                self.failures.append((fullpath, e))
        indexer.generateIndex()
        self.percentdone(1., None)

    def percentdone(self, percent, fname):
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
    return os.path.splitext(originalFileName)[0]+outputExtension

def fooAddingGenerator(originalFileName, outputExtension):
    return os.path.splitext(originalFileName)[0]+"foo"+outputExtension

def outputdirGenerator(originalFileName, outputExtension, inputdir, outputdir):
    originalFileName = os.path.abspath(originalFileName)
    abs_inputdir = os.path.abspath(inputdir)
    if os.path.commonprefix((originalFileName, abs_inputdir)) != abs_inputdir:
        raise ValueError("Original file name '" + originalFileName +
              "' not under input directory '" + abs_inputdir + "'")

    adjustedPath = os.path.join(outputdir, os.path.basename(originalFileName))
    return tree.getOutputFileName(adjustedPath, outputExtension)

def getFilenameGenerator(config, outputExt):
    if config.get('outputdir'):
        return (lambda originalFileName, outputExtension:
            outputdirGenerator(originalFileName, outputExtension,
                               os.path.abspath(config.get('inputdir')),
                               os.path.abspath(config.get('outputdir'))))
    else:
        return tree.getOutputFileName

def getProcessor(module, output, config):
    try:
        m = getattr(module.factory, 'generate_'+output)
    except AttributeError:
        raise NoProcessorError("cannot generate "+output+" output")

    if config.get('ext'):
        ext = config['ext']
    else:
        from default import htmlDefault
        ext = htmlDefault['ext']

    return m(config, getFilenameGenerator(config, ext))
