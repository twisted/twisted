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
import sys
from twisted.lore import process, default
from twisted.python import usage, plugin

class Options(usage.Options):

    optFlags = [["plain", 'p', "Report filenames without progress bar"]]

    optParameters = [
                     ["input", "i", 'lore'],
                     ["docsdir", "d", None],
                     ["linkrel", "l", ''],
                     ["output", "o", 'html'],
                    ]

    def __init__(self, *args, **kw):
        usage.Options.__init__(self, *args, **kw)
        self.config = {}

    def opt_config(self, s):
        if '=' in s:
            k, v = s.split('=', 1)
            self.config[k] = v
        else:
            self.config[s] = 1

    def parseArgs(self, *files):
        self['files'] = files



def run():
    opt = Options()
    try:
        opt.parseOptions()
    except usage.UsageError, errortext:
        print '%s: %s' % (sys.argv[0], errortext)
        print '%s: Try --help for usage details.' % sys.argv[0]
        sys.exit(1)
    plugins = plugin.getPlugIns("lore", 0, 0)
    for plug in plugins:
        if plug.tapname == opt['input']:
            module = plug
            break
    else:
        print '%s: no such input: %s' % (sys.argv[0], opt['input'])
        sys.exit(1)
    module = module.load()
    try:
        df = process.getProcessor(module, opt['output'], opt.config)
    except process.NoProcessorError, e:
        print "%s: %s" % (sys.argv[0], e)
        sys.exit(1)
    klass = process.Walker
    if opt['plain']: 
        klass = process.PlainReportingWalker
    w = klass(df, '.html', opt['linkrel'])
    if opt['files']:
        for fn in opt['files']:
            w.walked.append(('', fn))
    else:
        w.walkdir(opt['docsdir'] or '.')
    w.generate()
