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

from twisted.lore import tree, latex, lint
from twisted.web import microdom

htmlDefault = {'template': 'template.tpl', 'baseurl': '%s', 'ext': '.xhtml'}

class ProcessingFunctionFactory:

    def generate_html(self, d):
        n = htmlDefault.copy()
        n.update(d)
        d = n
        if d['ext'] == "None":
            ext = ""
        else:
            ext = d['ext']
        templ = microdom.parse(open(d['template']))
        df = lambda file, linkrel: tree.doFile(file, linkrel, d['ext'],
                                           d['baseurl'], templ)
        return df

    def generate_latex(self, d):
        if d.get('section'):
            df = lambda file, linkrel: latex.convertFile(file,
                                       latex.SectionLatexSpitter)
        else:
            df = lambda file, linkrel: latex.convertFile(file,
                                       latex.LatexSpitter)
        return df

    def generate_lint(self, d):
        checker = lint.getDefaultChecker()
        return lambda file, linkrel: lint.doFile(file, checker)

factory = ProcessingFunctionFactory()
