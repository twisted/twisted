
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
        optParameters = [["message", "m", "friend!"]]
        def __init__(self):
            self.debug = 0
        def opt_debug(self, opt):
            if opt == "yes" or opt == "y" or opt == "1":
                self.debug = 1
            elif opt == "no" or opt == "n" or opt == "0":
                self.debug = 0
            else:
                print "Unknown value for debug, setting to 0"
                self.debug = 0
        opt_d = opt_debug # a single-char alias for --debug
    try:
        config = MyOptions()
        config.parseOptions()
    except usage.UsageError, ue:
        print "%s: %s" % (sys.argv[0], ue)
    if config.hello:
        if config.debug: print "printing hello"
        print "hello", config.message #defaults to "friend!"
    if config.goodbye:
        if config.debug: print "printing goodbye"
        print "goodbye", config.message

#EOF

As you can see, you define optFlags as a list of parameters (with
both long and short names) that are either on or off.  optParameters
are parameters with string values, with their default value as
the third parameter in the list.  If you want to handle your own
options, define a method named opt_paramname that takes (self,
option) as arguments. option will be whatever immediately follows
the parameter on the command line. A few example command lines
that will work:

# XXX - Where'd the examples go?
""" # "

# System Imports
import string
import os
import sys
import new
import getopt
from os import path

# Sibling Imports
import reflect
import text


class UsageError(Exception):
    pass

error = UsageError

class Options:
    """
    A class which can be subclassed to provide command-line options
    to your program. See twisted.usage.__doc__ for for details.
    """

    def __init__(self):
        # These are strings/lists we will pass to getopt
        self.longOpt = []
        self.shortOpt = ''
        self.docs = {}
        self.synonyms = {}
        self.__dispatch = {}

        collectors = [
            self._gather_flags,
            self._gather_parameters,
            self._gather_handlers,
            ]

        for (longOpt, shortOpt, docs, settings, synonyms, dispatch)\
            in map( lambda c: c(), collectors):

            self.longOpt.extend(longOpt)
            self.shortOpt = self.shortOpt + shortOpt
            self.docs.update(docs)
            self.__dict__.update(settings)
            self.synonyms.update(synonyms)
            self.__dispatch.update(dispatch)

    def opt_help(self):
        print self.__str__()
        sys.exit(0)

    #opt_h = opt_help # this conflicted with existing 'host' options.

    def parseOptions(self, options=None):
        """The guts of the command-line parser.
        """

        if options is None:
            options = sys.argv[1:]

        try:
            opts, args = getopt.getopt(options,
                                       self.shortOpt, self.longOpt)
        except getopt.error, e:
            raise UsageError, e

        try:
            apply(self.parseArgs,args)
        except TypeError:
            raise UsageError("wrong number of arguments.")

        for opt, arg in opts:
            if opt[1] == '-':
                opt = opt[2:]
            else:
                opt = opt[1:]

            if not self.synonyms.has_key(opt):
                raise UsageError, "No such option '%s'" % (opt,)

            opt = self.synonyms[opt]
            self.__dispatch[opt](opt, arg)

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

    def _generic_flag(self, flagName, value=None):
        if value not in ('', None):
            raise UsageError, ("Flag '%s' takes no argument."
                               " Not even \"%s\"." % (flagName, value))
        setattr(self, flagName, 1)

    def _generic_parameter(self, parameterName, value):
        if value in ('', None):
            raise UsageError, ("Parameter '%s' requires an argument."
                               % (parameterName,))
        setattr(self, parameterName, value)

    def _gather_flags(self):
        """Gather up boolean (flag) options.
        """

        longOpt, shortOpt = [], ''
        docs, settings, synonyms, dispatch = {}, {}, {}, {}

        flags = []
        reflect.accumulateClassList(self.__class__, 'optFlags', flags)

        for flag in flags:
            long, short, doc = padTo(3, flag)
            if not long:
                raise ValueError, "A flag cannot be without a name."

            docs[long] = doc
            settings[long] = 0
            if short:
                shortOpt = shortOpt + short
                synonyms[short] = long
            longOpt.append(long)
            synonyms[long] = long
            dispatch[long] = self._generic_flag

        return longOpt, shortOpt, docs, settings, synonyms, dispatch


    def _gather_parameters(self):
        """Gather options which take a value.
        """
        longOpt, shortOpt = [], ''
        docs, settings, synonyms, dispatch = {}, {}, {}, {}

        parameters = []
        # We have to keep calling these "optStrings" because this code is
        # used in the IPC10 paper, which makes it written in stone...
        reflect.accumulateClassList(self.__class__, 'optStrings',
                                    parameters)

        # But since "strings" is a very poor description (yes, getopt
        # does happen to return the values as strings, but that's
        # irrelevant), provide another name that makes more sense.
        reflect.accumulateClassList(self.__class__, 'optParameters',
                                    parameters)

        synonyms = {}

        for parameter in parameters:
            long, short, default, doc = padTo(4, parameter)
            if not long:
                raise ValueError, "A parameter cannot be without a name."

            docs[long] = doc
            settings[long] = default
            if short:
                shortOpt = shortOpt + short + ':'
                synonyms[short] = long
            longOpt.append(long + '=')
            synonyms[long] = long
            dispatch[long] = self._generic_parameter

        return longOpt, shortOpt, docs, settings, synonyms, dispatch


    def _gather_handlers(self):
        """Gather up options with their own handler methods.
        """

        longOpt, shortOpt = [], ''
        docs, settings, synonyms, dispatch = {}, {}, {}, {}

        dct = {}
        reflect.addMethodNamesToDict(self.__class__, dct, "opt_")

        for name in dct.keys():
            method = getattr(self, 'opt_'+name)
            reqArgs = method.im_func.func_code.co_argcount
            if reqArgs > 2:
                raise UsageError('invalid Option function for %s' % name)
            if reqArgs == 2:
                # argName = method.im_func.func_code.co_varnames[1]
                takesArg = 1
            else:
                takesArg = 0

            doc = getattr(method, '__doc__', None)
            if doc:
                ## Only use the first line.
                #docs[name] = string.split(doc, '\n')[0]
                docs[name] = doc
            else:
                docs[name] = None

            synonyms[name] = name

            # A little slight-of-hand here makes dispatching much easier
            # in parseOptions, as it makes all option-methods have the
            # same signature.
            if takesArg:
                fn = lambda self, name, value, m=method: m(value)
            else:
                # XXX: This won't raise a TypeError if it's called
                # with a value when it shouldn't be.
                fn = lambda self, name, value=None, m=method: m()

            dispatch[name] = new.instancemethod(fn, self, self.__class__)

            if len(name) == 1:
                shortOpt = shortOpt + name
                if takesArg:
                    shortOpt = shortOpt + ':'
            else:
                if takesArg:
                    name = name + '='
                longOpt.append(name)

        reverse_dct = {}
        # Map synonyms
        for name in dct.keys():
            method = getattr(self, 'opt_'+name)
            if not reverse_dct.has_key(method):
                reverse_dct[method] = []
            reverse_dct[method].append(name)

        cmpLength = lambda a, b: cmp(len(a), len(b))

        for method, names in reverse_dct.items():
            if len(names) < 2:
                continue
            names_ = names[:]
            names_.sort(cmpLength)
            longest = names_.pop()
            for name in names_:
                synonyms[name] = longest

        return longOpt, shortOpt, docs, settings, synonyms, dispatch


    def __str__(self, width=None):
        if not width:
            width = int(os.environ.get('COLUMNS', '80'))

        longToShort = {}
        for key, value in self.synonyms.items():
            longname = value
            if (key != longname) and (len(key) == 1):
                longToShort[longname] = key
            else:
                if not longToShort.has_key(longname):
                    longToShort[longname] = None
                else:
                    pass

        optDicts = []
        for opt in self.longOpt:
            if opt[-1] == '=':
                optType = 'parameter'
                opt = opt[:-1]
            else:
                optType = 'flag'

            optDicts.append(
                {'long': opt,
                 'short': longToShort[opt],
                 'doc': self.docs[opt],
                 'optType': optType,
                 'default': getattr(self, opt, None)
                 })

        synopsis = getattr(self, "synopsis",
                           "Usage: %s%s"
                           % (path.basename(sys.argv[0]),
                              (optDicts and " [options]") or ''))

        if not synopsis[-len('\n'):] == '\n':
            synopsis = synopsis + '\n'

        if not (getattr(self, "longdesc", None) is None):
            longdesc = self.longdesc
        else:
            import __main__
            if getattr(__main__, '__doc__', None):
                longdesc = __main__.__doc__
            else:
                longdesc = ''

        if longdesc:
            longdesc = ('\n' +
                        string.join(text.wordWrap(longdesc, width), '\n'))

        if optDicts:
            chunks = docMakeChunks(optDicts, width)
            s = "Options:\n%s" % (string.join(chunks, ''))
        else:
            s = "Options: None\n"

        return synopsis + s + longdesc

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
            if opt.get('optType', None) != "flag":
                # these take up an extra character
                optLen = optLen + 1
            maxOptLen = max(optLen, maxOptLen)

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
        if opt.get('short', None):
            short = "-%c" % (opt['short'],)
        else:
            short = ''

        if opt.get('long', None):
            long = opt['long']
            if opt.get("optType", None) != "flag":
                long = long + '='

            long = "%-*s" % (maxOptLen, long)
            if short:
                comma = ","
        else:
            long = " " * (maxOptLen + len('--'))

        column1 = "  %2s%c --%s  " % (short, comma, long)

        if opt.get('doc', ''):
            doc = opt['doc']
        else:
            doc = ''

        if (opt.get("optType", None) != "flag") \
           and not (opt.get('default', None) is None):
            doc = "%s [default: %s]" % (doc, opt['default'])

        if doc:
            column2_l = text.wordWrap(doc, colWidth2)
        else:
            column2_l = ['']

        optLines.append("%s%s\n" % (column1, column2_l.pop(0)))

        for line in column2_l:
            optLines.append("%s%s\n" % (colFiller1, line))

        optChunks.append(string.join(optLines, ''))

    return optChunks


def padTo(n, seq, default=None):
    """Pads a sequence out to n elements,

    filling in with a default value if it is not long enough.

    If the input sequence is longer than n, raises ValueError.

    Details, details:
    This returns a new list; it does not extend the original sequence.
    The new list contains the values of the original sequence, not copies.
    """

    if len(seq) > n:
        raise ValueError, "%d elements is more than %d." % (len(seq), n)

    blank = [default] * n

    blank[:len(seq)] = list(seq)

    return blank
