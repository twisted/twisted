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
from __future__ import nested_scopes

from twisted.lore import tree, latex, lint, process
from twisted.web import microdom
from twisted.protocols import sux

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
