
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

"""
twisted.python.usage is a module for parsing/handling the
command line of your program. You use it by subclassing
Options with certain methods/attributes defined. Here's
an example::

    from twisted.python import usage
    import sys
    class MyOptions(usage.Options):
        optFlags = [["hello", "h"], ["goodbye", "g"]]
        optStrings = [["message", "m", "friend!"]]
        def __init__(self):
            self.debug = 0
        def opt_debug(self, opt):
            if opt == "yes" or opt == "y" or opt == "1":
                self.debug = 1
            elif opt == "no" or opt == "n" or opt == "0":
                self.debug = 0
            else:
                print "Unkown value for debug, setting to 0"
                self.debug = 0
        opt_d = opt_debug # a single-char alias for --debug
    try:
        config = MyOptions()
        config.parseOptions()
    except usage.error, ue:
        print "%s: %s" % (sys.argv[0], ue)
    if config.hello:
        if config.debug: print "printing hello"
        print "hello", config.message #defaults to "friend!"
    if config.goodbye:
        if config.debug: print "printing goodbye"
        print "goodbye", config.message

#EOF

As you can see, you define optFlags as a list of paramaters (with
both long and short names) that are either on or off.  optStrings
are paramaters with string values, with their default value as
the third parameter in the list.  If you want to handle your own
options, define a method named opt_paramname that takes (self,
option) as paramaters. option will be whatever immediately follows
the paramater on the command line. A few example command lines
that will work:

# XXX - Where'd the examples go?
"""

# System Imports
import string
import os
import sys
import getopt

# Sibling Imports
import reflect
import text

error = getopt.error

class Options:
    """
    A class which can be subclassed to provide command-line options
    to your program. See twisted.usage.__doc__ for for details.
    """
    def parseOptions(self, options=None):
        """
        The guts of the command-line parser.
        """
        # it's fine if this is slow
        if options is None:
            options = sys.argv[1:]
        dct = {}
        reflect.addMethodNamesToDict(self.__class__, dct, "opt_")
        # optDoc = {}
        # These are strings/lists we will pass to getopt
        shortOpt = ''
        longOpt = []

        for name in dct.keys():
            method = getattr(self, 'opt_'+name)
            reqArgs = method.im_func.func_code.co_argcount
            if reqArgs > 2:
                raise error, 'invalid Option function for %s' % name
            if reqArgs == 2:
                takesArg = 1
            else:
                takesArg = 0

            if len(name) == 1:
                shortOpt = shortOpt + name
                if takesArg:
                    shortOpt = shortOpt + ':'
            else:
                if takesArg:
                    name = name + '='
                longOpt.append(name)

        flags = []
        reflect.accumulateClassList(self.__class__, 'optFlags', flags)
        strings = []
        reflect.accumulateClassList(self.__class__, 'optStrings', strings)
        flagDict = {}
        stringDict = {}

        for flag in flags:
            long, short = flag[:2]
            # The doc parameter is optional to preserve compatibility.
            if len(flag) == 2:
                pass # optDoc[long] = None
            elif len(flag) == 3:
                pass # optDoc[long] = flag[3]
            else:
                raise ValueError,\
                      "Too many parameters for flag %s" % (long,)
            setattr(self, long, 0)
            if short:
                shortOpt = shortOpt + short
            longOpt.append(long)
            flagDict[short] = long
            flagDict[long] = long

        for string_ in strings:
            long, short, default = string_[:3]
            # The doc parameter is optional to preserve compatibility.
            if len(string_) == 3:
                pass # optDoc[long] = None
            elif len(string_) == 4:
                pass # optDoc[long] = string_[4]
            else:
                raise ValueError,\
                      "Too many parameters for option string %s" % (long,)
            setattr(self, long, default)
            if short:
                shortOpt = shortOpt + short + ':'
            longOpt.append(long + '=')
            stringDict[short] = long
            stringDict[long] = long

        opts, args = getopt.getopt(options,shortOpt,longOpt)

        try:
            apply(self.parseArgs,args)
        except TypeError:
            raise error, "wrong number of arguments."
        for opt, arg in opts:
            if opt[1] == '-':
                opt = opt[2:]
            else:
                opt = opt[1:]
            if flagDict.has_key(opt):
                assert arg == '', 'This option is a flag.'
                setattr(self, flagDict[opt], 1)
            elif stringDict.has_key(opt):
                setattr(self, stringDict[opt], arg)
            else:
                method = getattr(self, 'opt_'+opt)
                if method.im_func.func_code.co_argcount == 2:
                    method(arg)
                else:
                    assert arg == '', "This option takes no arguments."
                    method()
        self.postOptions()

    def postOptions(self):
        """I am called after the options are parsed.

        Override this method in your subclass to do something after
        the options have been parsed and assigned.

        XXX: Like what?
        """
        pass

    def parseArgs(self):
        """I am called with any leftover arguments which were not options.

        Override me to do something with the remaining arguments on
        the command line, those which were not flags or options. e.g.
        interpret them as a list of files to operate on.

        Note that if there more arguments on the command line
        than this method accepts, parseArgs will blow up with
        a getopt.error.  This means if you don't override me,
        parseArgs will blow up if I am passed any arguments at
        all!
        """
        pass


    def __str__(self, width=None):
        if not width:
            width = int(os.getenv('COLUMNS', '80'))

        flags = []
        reflect.accumulateClassList(self.__class__, 'optFlags', flags)
        strings = []
        reflect.accumulateClassList(self.__class__, 'optStrings', strings)

        # We should have collected these into some sane container
        # earlier...
        optDicts = []
        for flag in flags:
            long, short = flag[:2]
            # The doc parameter is optional to preserve compatibility.
            if len(flag) == 2:
                doc = None
            elif len(flag) == 3:
                doc = flag[2]
            else:
                raise ValueError,\
                      "Too many parameters for flag %s" % (long,)
            d = {'long': long,
                 'short': short,
                 'doc': doc,
                 'optType': 'flag'}
            optDicts.append(d)

        for string_ in strings:
            long, short, default = string_[:3]
            # The doc parameter is optional to preserve compatibility.
            if len(string_) == 3:
                doc = None
            elif len(string_) == 4:
                doc = string_[3]
            else:
                raise ValueError,\
                      "Too many parameters for option string %s" % (long,)

            d = {'long': long,
                 'short': short,
                 'default': default,
                 'doc': doc,
                 'optType': 'string'}
            optDicts.append(d)

        # XXX: Decide how user-defined opt_Foo methods fit in to this.

        if optDicts:
            chunks = docMakeChunks(optDicts, width)
            s = "Options:\n%s" % (string.join(chunks, ''))
        else:
            s = "Options: None\n"

        return s

    #def __repr__(self):
    #    XXX: It'd be cool if we could return a succinct representation
    #        of which flags and options are set here.


def docMakeChunks(optList, width=80):
    """Makes doc chunks for option declarations.

    Takes a list of dictionaries, each of which may have one or more
    of the keys "long", "short", "doc", "default", "optType".

    Returns a list of strings.
    The strings may be multiple lines,
    all of them end with a newline.
    """

    # XXX: sanity check to make sure we have a sane combination of keys.

    maxOptLen = 0
    for opt in optList:
        optLen = len(opt.get('long', ''))
        if optLen:
            if opt.get('optType', None) == "string":
                # these take up an extra character
                optLen = optLen + 1
            maxOptLen = max(len(opt.get('long', '')), maxOptLen)

    colWidth1 = maxOptLen + len("  -s, --  ")
    colWidth2 = width - colWidth1
    # XXX - impose some sane minimum limit.
    # Then if we don't have enough room for the option and the doc
    # to share one line, they can take turns on alternating lines.

    colFiller1 = " " * colWidth1

    optChunks = []
    for opt in optList:
        optLines = []
        comma = " "
        short = "%c" % (opt.get('short', None) or " ",)

        if opt.get('long', None):
            if opt.get("optType", None) == "string":
                takesString = "="
            else:
                takesString = ''

            long = "%-*s%s" % (maxOptLen, opt['long'], takesString)
            if short != " ":
                comma = ","
        else:
            long = " " * (maxOptLen + len('--'))

        column1 = "  -%c%c --%s  " % (short, comma, long)

        if opt.get('doc', None):
            if opt.get('default', None):
                doc = "%s [%s]" % (opt['doc'], opt['default'])
            else:
                doc = opt['doc']
            column2_l = text.wordWrap(doc, colWidth2)
        else:
            column2_l = ['']

        optLines.append("%s%s\n" % (column1, column2_l.pop(0)))

        for line in column2_l:
            optLines.append("%s%s\n" % (colFiller1, line))

        optChunks.append(string.join(optLines, ''))

    return optChunks
