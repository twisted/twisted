# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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
from __future__ import nested_scopes

import sys
from twisted.lore import process
from twisted.python import usage

class Options(usage.Options):

    optParameters = [
                     ["docsdir", "d", None],
                     ["linkrel", "l", ''],
                     ["template", "t", "template.tpl",
                      "The template to follow for generating content."],
                     ["ext", "e", ".xhtml",
                      "The extension of output files (and thus what links are "
                      "munged to)"],
                     ["baseurl", "u", '%s',
                      "The URL that API-ref links are to use, with %s for "
                      "the module or class"]]

    def parseArgs(self, *files):
        self['files'] = files


def makeProcessingFunction(d):
    from twisted.lore import tree
    from twisted.web import microdom
    if d['ext'] == "None":
        ext = ""
    else:
        ext = d['ext']
    templ = microdom.parse(open(d['template']))
    df = lambda file, linkrel: tree.doFile(file, linkrel, d['ext'],
                                           d['baseurl'], templ)
    return df


def run():
    opt = Options()
    try:
        opt.parseOptions()
    except usage.UsageError, errortext:
        print '%s: %s' % (sys.argv[0], errortext)
        print '%s: Try --help for usage details.' % (sys.argv[0])
        sys.exit(1)
    df = makeProcessingFunction(opt)
    w = process.Walker(df, '.html', opt['linkrel'])
    if opt['files']:
        for fn in opt['files']:
            w.walked.append(('', fn))
    else:
        w.walkdir(opt['docsdir'] or '.')
    w.generate()
    print
