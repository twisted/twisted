# -*- test-case-name: twisted.test.test_lore -*-
# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
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

    def walkdir(self, topdir):
        self.basecount = dircount(topdir)
        os.path.walk(topdir, self.walk, None)

    def walk(self, ig, d, names):
        linkrel = '../' * (dircount(d) - self.basecount)
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
    if os.path.commonprefix((originalFileName, inputdir)) != inputdir:
        raise ValueError("Original file name '" + originalFileName +
              "' not under input directory '" + inputdir + "'")

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
