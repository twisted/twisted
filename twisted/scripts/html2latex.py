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

import sys
from twisted.lore import process
from twisted.python import usage

class Options(usage.Options):

    optFlags = [["plain", 'p', "Report filenames without progress bar"],
                ["section", 's', "Generate a section, not an article"]]

    optParameters = [["docsdir", "d", None]]

    def parseArgs(self, *files):
        self['files'] = files


def makeProcessingFunction(d):
    from twisted.lore import default
    return process.getProcessor(default, 'latex', d)

def run():
    opt = Options()
    try:
        opt.parseOptions()
    except usage.UsageError, errortext:
        print '%s: %s' % (sys.argv[0], errortext)
        print '%s: Try --help for usage details.' % sys.argv[0]
        sys.exit(1)
    df = makeProcessingFunction(opt)
    klass = process.Walker
    if opt['plain']: 
        klass = process.PlainReportingWalker
    w = klass(df, '.html', '')
    if opt['files']:
        for fn in opt['files']:
            w.walked.append(('', fn))
    else:
        w.walkdir(opt['docsdir'] or '.')
    w.generate()
