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
from twisted.lore import process, default, indexer, numberer, htmlbook
from twisted.python import usage, plugin, reflect

class Options(usage.Options):

    optFlags = [["plain", 'p', "Report filenames without progress bar"],
                ["null", 'n', "Do not report filenames"],
                ["number", 'N', "Add chapter/section numbers to section headings"],
]

    optParameters = [
                     ["input", "i", 'lore'],
                     ["inputext", "e", ".xhtml", "The extension that your Lore input files have"],
                     ["docsdir", "d", None],
                     ["linkrel", "l", ''],
                     ["output", "o", 'html'],
                     ["index", "x", None, "The base filename you want to give your index file"],
                     ["book", "b", None, "The book file to generate a book from"],
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


def getProcessor(input, output, config):
    plugins = plugin.getPlugIns("lore", None, None)
    for plug in plugins:
        if plug.tapname == input:
            module = plug.load()
            break
    else:
        # try treating it as a module name
        try:
            module = reflect.namedModule(input)
        except ImportError:
            print '%s: no such input: %s' % (sys.argv[0], input)
            return
    try:
        return process.getProcessor(module, output, config)
    except process.NoProcessorError, e:
        print "%s: %s" % (sys.argv[0], e)


def getWalker(df, opt):
    klass = process.Walker
    if opt['plain']: 
        klass = process.PlainReportingWalker
    if opt['null']: 
        klass = process.NullReportingWalker
    return klass(df, opt['inputext'], opt['linkrel'])


def runGivenOptions(opt):
    """Do everything but parse the options; useful for testing.
    Returns a descriptive string if there's an error."""

    book = None
    if opt['book']:
        book = htmlbook.Book(opt['book'])

    df = getProcessor(opt['input'], opt['output'], opt.config)
    if not df:
        return 'getProcessor() failed'

    walker = getWalker(df, opt)

    if opt['files']:
        for filename in opt['files']:
            walker.walked.append(('', filename))
    elif book:
        for filename in book.getFiles():
            walker.walked.append(('', filename))
    else:
        walker.walkdir(opt['docsdir'] or '.')

    if opt['index']:
        indexFilename = opt['index']
    elif book:
        indexFilename = book.getIndexFilename()
    else:
        indexFilename = None

    if indexFilename:
        indexer.setIndexFilename("%s.%s" % (indexFilename, opt['output']))
    else:
        indexer.setIndexFilename(None)

    ## TODO: get numberSections from book, if any
    numberer.setNumberSections(opt['number'])

    walker.generate()

    if walker.failures:
        for (file, errors) in walker.failures:
            for error in errors:
                print "%s:%s" % (file, error)
        return 'Walker failures'


def run():
    opt = Options()
    try:
        opt.parseOptions()
    except usage.UsageError, errortext:
        print '%s: %s' % (sys.argv[0], errortext)
        print '%s: Try --help for usage details.' % sys.argv[0]
        sys.exit(1)

    result = runGivenOptions(opt)
    if result:
        print result
        sys.exit(1)


if __name__ == '__main__':
    run()

