# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
from __future__ import nested_scopes

from twisted.lore import tree, latex, lint, process
from twisted.web import sux, microdom

htmlDefault = {'template': 'template.tpl', 'baseurl': '%s', 'ext': '.html'}

class ProcessingFunctionFactory:

    def getDoFile(self):
        return tree.doFile

    def generate_html(self, options, filenameGenerator=tree.getOutputFileName):
        n = htmlDefault.copy()
        n.update(options)
        options = n
        try:
            fp = open(options['template'])
            templ = microdom.parse(fp)
        except IOError, e:
            raise process.NoProcessorError(e.filename+": "+e.strerror)
        except sux.ParseError, e:
            raise process.NoProcessorError(str(e))
        df = lambda file, linkrel: self.getDoFile()(file, linkrel, options['ext'],
                                                    options['baseurl'], templ, options, filenameGenerator)
        return df

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
        df = lambda file, linkrel: latex.convertFile(file, spitter)
        return df

    def getLintChecker(self):
        return lint.getDefaultChecker()

    def generate_lint(self, options, filenameGenerator=None):
        checker = self.getLintChecker()
        return lambda file, linkrel: lint.doFile(file, checker)

factory = ProcessingFunctionFactory()
