# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implementation of the lore command line program.
"""

import sys

from zope.interface import Interface, Attribute

from twisted.lore import process, htmlbook
from twisted.lore.indexer import Indexer, TableOfContents
from twisted.lore.numberer import Numberer

from twisted.python import usage, plugin as oldplugin, reflect
from twisted import plugin as newplugin


class IProcessor(Interface):
    """
    A lore document transformation plugin.

    Processors provide generators for different output formats.
    """

    factory = Attribute(
        """
        An object with I{generate_}-prefixed methods for each output format
        supported.  For example, to customize HTML output, this object should
        define a method named C{generate_html}.
        """)



class Options(usage.Options):

    optFlags = [
        ["plain", 'p', "Report filenames without progress bar"],
        ["null", 'n', "Do not report filenames"],
        ["number", 'N', "Add chapter/section numbers to section headings"]]

    optParameters = [
        ["input", "i", 'lore'],
        ["inputext", "e", ".xhtml",
         "The extension that your Lore input files have"],
        ["docsdir", "d", None],
        ["linkrel", "l", ''],
        ["output", "o", 'html'],
        ["index", "x", None,
         "The base filename you want to give your index file"],
        ["book", "b", None, "The book file to generate a book from"],
        ["prefixurl", None, "",
         "The prefix to stick on to relative links; only useful when "
         "processing directories"]]

    #zsh_altArgDescr = {"foo":"use this description for foo instead"}
    #zsh_multiUse = ["foo", "bar"]
    #zsh_mutuallyExclusive = [("foo", "bar"), ("bar", "baz")]
    #zsh_actions = {"foo":'_files -g "*.foo"', "bar":"(one two three)"}
    #zsh_actionDescr = {"logfile":"log file name", "random":"random seed"}
    zsh_extras = ["*:files:_files"]


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



def _getProcessorModule(input, output, config):
    """
    Find the module capable of processing the specified input type.

    @type input: C{str}
    @param input: A string describing the input format.  eg, C{'html'}.
    """
    plugins = oldplugin._getPlugIns("lore")
    for plug in plugins:
        if plug.tapname == input:
            return plug.load()
    else:
        plugins = newplugin.getPlugins(IProcessor)
        for plug in plugins:
            if plug.name == input:
                return reflect.namedModule(plug.moduleName)
        else:
            # try treating it as a module name
            try:
                return reflect.namedModule(input)
            except ImportError:
                print '%s: no such input: %s' % (sys.argv[0], input)
                return



def getProcessor(input, output, config):
    """
    Get the generate method of an output generator for the specified input and
    output formats.

    @return: A callable like L{HTMLGenerator.generate}
    """
    # XXX deprecate this
    module = _getProcessorModule(input, output, config)
    if module is None:
        return None
    try:
        return process.getProcessor(module, output, config)
    except process.NoProcessorError, e:
        print "%s: %s" % (sys.argv[0], e)



def getGenerator(input, output, config):
    """
    Get an output generator for the specified input and output formats.

    @return: An instance of a class like L{HTMLGenerator}.
    """
    module = _getProcessorModule(input, output, config)
    if module is None:
        return None
    return process.getOutputGenerator(module, output, config)



def getWalker(generator, opt):
    """
    Get a visitor appropriate for the specified options.
    """
    klass = process.Walker
    if opt['plain']:
        klass = process.PlainReportingWalker
    if opt['null']:
        klass = process.NullReportingWalker
    return klass(
        generator,
        opt['inputext'], opt['linkrel'],
        opt.config['template'])



def runGivenOptions(opt):
    """
    Do everything but parse the options; useful for testing.  Returns a
    descriptive string if there's an error.
    """
    book = None
    if opt['book']:
        book = htmlbook.Book(opt['book'])

    indexer = Indexer()
    toc = TableOfContents()

    generator = getGenerator(opt['input'], opt['output'], opt.config)
    if generator is None:
        # XXX Not an awesome return value
        return 'getProcessor() failed'

    walker = getWalker(generator, opt)

    if opt['files']:
        for filename in opt['files']:
            walker.walked.append(('', filename))
    elif book is not None:
        for filename in book.getFiles():
            walker.walked.append(('', filename))
    else:
        walker.walkdir(opt['docsdir'] or '.', opt['prefixurl'])

    if opt['index']:
        indexFilename = opt['index']
    elif book is not None:
        indexFilename = book.getIndexFilename()
    else:
        indexFilename = None

    if indexFilename:
        indexer.setIndexFilename("%s.%s" % (indexFilename, opt['output']))
    else:
        indexer.setIndexFilename(None)

    ## TODO: get numberSections from book, if any
    numberer = Numberer()
    numberer.numberSections = opt['number']

    walker.generate(book, indexer, toc, numberer)

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

