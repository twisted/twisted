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

import sys, os
from twisted.lore import tree
from twisted.python import usage
from twisted.web import microdom

cols = 79

def dircount(d):
    return len([1 for el in d.split("/") if el != '.'])


class Walker:

    def __init__(self, templ, baseurl, ext, linkrel):
        self.templ = templ
        self.baseurl = baseurl
        self.ext = ext
        self.linkrel = linkrel
        self.walked = []

    def walkdir(self, topdir):
        self.basecount = dircount(topdir)
        os.path.walk(topdir, self.walk, None)
        self.walkAround()

    def walk(self, ig, d, names):
        linkrel = '../' * (dircount(d) - self.basecount)
        for name in names:
            fullpath = os.path.join(d, name)
            fname, fext = os.path.splitext(fullpath)
            if fext == '.html':
                self.walked.append((linkrel, fname, fullpath, d))
                
    def walkAround(self):
        i = 0
        for linkrel, fname, fullpath, d in self.walked:
            linkrel = self.linkrel + linkrel
            i += 1
            self.percentdone((float(i) / len(self.walked)), fname)
            tree.doFile(fullpath, d, self.ext, self.baseurl, self.templ,linkrel)
        self.percentdone(1., "*Done*")

    def percentdone(self, percent, fname):
        # override for neater progress bars
        proglen = 40
        hashes = int(percent * proglen)
        spaces = proglen - hashes
        progstat = "[%s%s] (%s)" %('#' * hashes, ' ' * spaces,fname)
        progstat += (cols - len(progstat)) * ' '
        progstat += '\r'
        sys.stdout.write(progstat)
        sys.stdout.flush()

class Options(usage.Options):

    optParameters = [["template", "t", "template.tpl",
                      "The template to follow for generating content."],
                     ["docsdir", "d", None],
                     ["linkrel", "l", ''],
                     ["ext", "e", ".xhtml",
                      "The extension of output files (and thus what links are "
                      "munged to)"],
                     ["baseurl", "u", '%s',
                      "The URL that API-ref links are to use, with %s for "
                      "the module or class"]]

    def parseArgs(self, *files):
        self['files'] = files


def run():
    opt = Options()
    try:
        opt.parseOptions()
    except usage.UsageError, errortext:
        print '%s: %s' % (sys.argv[0], errortext)
        print '%s: Try --help for usage details.' % (sys.argv[0])
        sys.exit(1)
    if opt['ext'] == "None":
        ext = ""
    else:
        ext = opt['ext']
    templ = microdom.parse(open(opt['template']))
    if opt['files']:
        for fn in opt['files']:
            tree.doFile(fn, opt['docsdir'] or os.path.dirname(fn),
                        ext, opt['baseurl'], templ, opt['linkrel'])
    else:
        w = Walker(templ, opt['baseurl'], ext, opt['linkrel'])
        w.walkdir(opt['docsdir'] or '.')
        print
