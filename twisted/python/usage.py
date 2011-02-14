# -*- test-case-name: twisted.test.test_usage -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
twisted.python.usage is a module for parsing/handling the
command line of your program.

For information on how to use it, see
U{http://twistedmatrix.com/projects/core/documentation/howto/options.html},
or doc/howto/options.html in your Twisted directory.
"""

# System Imports
import os
import sys
import getopt
from os import path

# Sibling Imports
from twisted.python import reflect, text, util


class UsageError(Exception):
    pass


error = UsageError


class CoerceParameter(object):
    """
    Utility class that can corce a parameter before storing it.
    """
    def __init__(self, options, coerce):
        """
        @param options: parent Options object
        @param coerce: callable used to coerce the value.
        """
        self.options = options
        self.coerce = coerce
        self.doc = getattr(self.coerce, 'coerceDoc', '')

    def dispatch(self, parameterName, value):
        """
        When called in dispatch, do the coerce for C{value} and save the
        returned value.
        """
        if value is None:
            raise UsageError("Parameter '%s' requires an argument."
                             % (parameterName,))
        try:
            value = self.coerce(value)
        except ValueError, e:
            raise UsageError("Parameter type enforcement failed: %s" % (e,))

        self.options.opts[parameterName] = value


class Options(dict):
    """
    An option list parser class

    C{optFlags} and C{optParameters} are lists of available parameters
    which your program can handle. The difference between the two
    is the 'flags' have an on(1) or off(0) state (off by default)
    whereas 'parameters' have an assigned value, with an optional
    default. (Compare '--verbose' and '--verbosity=2')

    optFlags is assigned a list of lists. Each list represents
    a flag parameter, as so::

    |    optFlags = [['verbose', 'v', 'Makes it tell you what it doing.'],
    |                ['quiet', 'q', 'Be vewy vewy quiet.']]

    As you can see, the first item is the long option name
    (prefixed with '--' on the command line), followed by the
    short option name (prefixed with '-'), and the description.
    The description is used for the built-in handling of the
    --help switch, which prints a usage summary.

    C{optParameters} is much the same, except the list also contains
    a default value::

    | optParameters = [['outfile', 'O', 'outfile.log', 'Description...']]

    A coerce function can also be specified as the last element: it will be
    called with the argument and should return the value that will be stored
    for the option. This function can have a C{coerceDoc} attribute which
    will be appended to the documentation of the option.

    subCommands is a list of 4-tuples of (command name, command shortcut,
    parser class, documentation).  If the first non-option argument found is
    one of the given command names, an instance of the given parser class is
    instantiated and given the remainder of the arguments to parse and
    self.opts[command] is set to the command name.  For example::

    | subCommands = [
    |      ['inquisition', 'inquest', InquisitionOptions,
    |           'Perform an inquisition'],
    |      ['holyquest', 'quest', HolyQuestOptions,
    |           'Embark upon a holy quest']
    |  ]

    In this case, C{"<program> holyquest --horseback --for-grail"} will cause
    C{HolyQuestOptions} to be instantiated and asked to parse
    C{['--horseback', '--for-grail']}.  Currently, only the first sub-command
    is parsed, and all options following it are passed to its parser.  If a
    subcommand is found, the subCommand attribute is set to its name and the
    subOptions attribute is set to the Option instance that parses the
    remaining options. If a subcommand is not given to parseOptions,
    the subCommand attribute will be None. You can also mark one of
    the subCommands to be the default.

    | defaultSubCommand = 'holyquest'

    In this case, the subCommand attribute will never be None, and
    the subOptions attribute will always be set.

    If you want to handle your own options, define a method named
    C{opt_paramname} that takes C{(self, option)} as arguments. C{option}
    will be whatever immediately follows the parameter on the
    command line. Options fully supports the mapping interface, so you
    can do things like C{'self["option"] = val'} in these methods.

    Advanced functionality is covered in the howto documentation,
    available at
    U{http://twistedmatrix.com/projects/core/documentation/howto/options.html},
    or doc/howto/options.html in your Twisted directory.
    """

    subCommand = None
    defaultSubCommand = None
    parent = None
    def __init__(self):
        super(Options, self).__init__()

        self.opts = self
        self.defaults = {}

        # These are strings/lists we will pass to getopt
        self.longOpt = []
        self.shortOpt = ''
        self.docs = {}
        self.synonyms = {}
        self._dispatch = {}


        collectors = [
            self._gather_flags,
            self._gather_parameters,
            self._gather_handlers,
            ]

        for c in collectors:
            (longOpt, shortOpt, docs, settings, synonyms, dispatch) = c()
            self.longOpt.extend(longOpt)
            self.shortOpt = self.shortOpt + shortOpt
            self.docs.update(docs)

            self.opts.update(settings)
            self.defaults.update(settings)

            self.synonyms.update(synonyms)
            self._dispatch.update(dispatch)

    def __hash__(self):
        """
        Define a custom hash function so that Options instances can be used
        as dictionary keys.  This is an internal feature used to implement
        the parser.  Do not rely on it in application code.
        """
        return int(id(self) % sys.maxint)

    def opt_help(self):
        """
        Display this help and exit.
        """
        print self.__str__()
        sys.exit(0)

    def opt_version(self):
        from twisted import copyright
        print "Twisted version:", copyright.version
        sys.exit(0)

    #opt_h = opt_help # this conflicted with existing 'host' options.

    def parseOptions(self, options=None):
        """
        The guts of the command-line parser.
        """

        if options is None:
            options = sys.argv[1:]
        try:
            opts, args = getopt.getopt(options,
                                       self.shortOpt, self.longOpt)
        except getopt.error, e:
            raise UsageError(str(e))

        for opt, arg in opts:
            if opt[1] == '-':
                opt = opt[2:]
            else:
                opt = opt[1:]

            optMangled = opt
            if optMangled not in self.synonyms:
                optMangled = opt.replace("-", "_")
                if optMangled not in self.synonyms:
                    raise UsageError("No such option '%s'" % (opt,))

            optMangled = self.synonyms[optMangled]
            if isinstance(self._dispatch[optMangled], CoerceParameter):
                self._dispatch[optMangled].dispatch(optMangled, arg)
            else:
                self._dispatch[optMangled](optMangled, arg)

        if (getattr(self, 'subCommands', None)
            and (args or self.defaultSubCommand is not None)):
            if not args:
                args = [self.defaultSubCommand]
            sub, rest = args[0], args[1:]
            for (cmd, short, parser, doc) in self.subCommands:
                if sub == cmd or sub == short:
                    self.subCommand = cmd
                    self.subOptions = parser()
                    self.subOptions.parent = self
                    self.subOptions.parseOptions(rest)
                    break
            else:
                raise UsageError("Unknown command: %s" % sub)
        else:
            try:
                self.parseArgs(*args)
            except TypeError:
                raise UsageError("Wrong number of arguments.")

        self.postOptions()

    def postOptions(self):
        """
        I am called after the options are parsed.

        Override this method in your subclass to do something after
        the options have been parsed and assigned, like validate that
        all options are sane.
        """

    def parseArgs(self):
        """
        I am called with any leftover arguments which were not options.

        Override me to do something with the remaining arguments on
        the command line, those which were not flags or options. e.g.
        interpret them as a list of files to operate on.

        Note that if there more arguments on the command line
        than this method accepts, parseArgs will blow up with
        a getopt.error.  This means if you don't override me,
        parseArgs will blow up if I am passed any arguments at
        all!
        """

    def _generic_flag(self, flagName, value=None):
        if value not in ('', None):
            raise UsageError("Flag '%s' takes no argument."
                             " Not even \"%s\"." % (flagName, value))

        self.opts[flagName] = 1

    def _gather_flags(self):
        """
        Gather up boolean (flag) options.
        """

        longOpt, shortOpt = [], ''
        docs, settings, synonyms, dispatch = {}, {}, {}, {}

        flags = []
        reflect.accumulateClassList(self.__class__, 'optFlags', flags)

        for flag in flags:
            long, short, doc = util.padTo(3, flag)
            if not long:
                raise ValueError("A flag cannot be without a name.")

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
        """
        Gather options which take a value.
        """
        longOpt, shortOpt = [], ''
        docs, settings, synonyms, dispatch = {}, {}, {}, {}

        parameters = []

        reflect.accumulateClassList(self.__class__, 'optStrings',
                                    parameters)
        if parameters:
            import warnings
            warnings.warn("Options.optStrings is deprecated, "
                          "please use optParameters instead.", stacklevel=2)

        reflect.accumulateClassList(self.__class__, 'optParameters',
                                    parameters)

        synonyms = {}

        for parameter in parameters:
            long, short, default, doc, paramType = util.padTo(5, parameter)
            if not long:
                raise ValueError("A parameter cannot be without a name.")

            docs[long] = doc
            settings[long] = default
            if short:
                shortOpt = shortOpt + short + ':'
                synonyms[short] = long
            longOpt.append(long + '=')
            synonyms[long] = long
            if paramType is not None:
                dispatch[long] = CoerceParameter(self, paramType)
            else:
                dispatch[long] = CoerceParameter(self, str)

        return longOpt, shortOpt, docs, settings, synonyms, dispatch


    def _gather_handlers(self):
        """
        Gather up options with their own handler methods.

        This returns a tuple of many values.  Amongst those values is a
        synonyms dictionary, mapping all of the possible aliases (C{str})
        for an option to the longest spelling of that option's name
        C({str}).

        Another element is a dispatch dictionary, mapping each user-facing
        option name (with - substituted for _) to a callable to handle that
        option.
        """

        longOpt, shortOpt = [], ''
        docs, settings, synonyms, dispatch = {}, {}, {}, {}

        dct = {}
        reflect.addMethodNamesToDict(self.__class__, dct, "opt_")

        for name in dct.keys():
            method = getattr(self, 'opt_'+name)

            takesArg = not flagFunction(method, name)

            prettyName = name.replace('_', '-')
            doc = getattr(method, '__doc__', None)
            if doc:
                ## Only use the first line.
                #docs[name] = doc.split('\n')[0]
                docs[prettyName] = doc
            else:
                docs[prettyName] = self.docs.get(prettyName)

            synonyms[prettyName] = prettyName

            # A little slight-of-hand here makes dispatching much easier
            # in parseOptions, as it makes all option-methods have the
            # same signature.
            if takesArg:
                fn = lambda name, value, m=method: m(value)
            else:
                # XXX: This won't raise a TypeError if it's called
                # with a value when it shouldn't be.
                fn = lambda name, value=None, m=method: m()

            dispatch[prettyName] = fn

            if len(name) == 1:
                shortOpt = shortOpt + name
                if takesArg:
                    shortOpt = shortOpt + ':'
            else:
                if takesArg:
                    prettyName = prettyName + '='
                longOpt.append(prettyName)

        reverse_dct = {}
        # Map synonyms
        for name in dct.keys():
            method = getattr(self, 'opt_' + name)
            if method not in reverse_dct:
                reverse_dct[method] = []
            reverse_dct[method].append(name.replace('_', '-'))

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


    def __str__(self):
        return self.getSynopsis() + '\n' + self.getUsage(width=None)

    def getSynopsis(self):
        """
        Returns a string containing a description of these options and how to
        pass them to the executed file.
        """

        default = "%s%s" % (path.basename(sys.argv[0]),
                            (self.longOpt and " [options]") or '')
        if self.parent is None:
            default = "Usage: %s%s" % (path.basename(sys.argv[0]),
                                       (self.longOpt and " [options]") or '')
        else:
            default = '%s' % ((self.longOpt and "[options]") or '')
        synopsis = getattr(self, "synopsis", default)

        synopsis = synopsis.rstrip()

        if self.parent is not None:
            synopsis = ' '.join((self.parent.getSynopsis(),
                                 self.parent.subCommand, synopsis))

        return synopsis

    def getUsage(self, width=None):
        # If subOptions exists by now, then there was probably an error while
        # parsing its options.
        if hasattr(self, 'subOptions'):
            return self.subOptions.getUsage(width=width)

        if not width:
            width = int(os.environ.get('COLUMNS', '80'))

        if hasattr(self, 'subCommands'):
            cmdDicts = []
            for (cmd, short, parser, desc) in self.subCommands:
                cmdDicts.append(
                    {'long': cmd,
                     'short': short,
                     'doc': desc,
                     'optType': 'command',
                     'default': None
                    })
            chunks = docMakeChunks(cmdDicts, width)
            commands = 'Commands:\n' + ''.join(chunks)
        else:
            commands = ''

        longToShort = {}
        for key, value in self.synonyms.items():
            longname = value
            if (key != longname) and (len(key) == 1):
                longToShort[longname] = key
            else:
                if longname not in longToShort:
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
                 'default': self.defaults.get(opt, None),
                 'dispatch': self._dispatch.get(opt, None)
                 })

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
                        '\n'.join(text.wordWrap(longdesc, width)).strip()
                        + '\n')

        if optDicts:
            chunks = docMakeChunks(optDicts, width)
            s = "Options:\n%s" % (''.join(chunks))
        else:
            s = "Options: None\n"

        return s + longdesc + commands

    #def __repr__(self):
    #    XXX: It'd be cool if we could return a succinct representation
    #        of which flags and options are set here.


def docMakeChunks(optList, width=80):
    """
    Makes doc chunks for option declarations.

    Takes a list of dictionaries, each of which may have one or more
    of the keys 'long', 'short', 'doc', 'default', 'optType'.

    Returns a list of strings.
    The strings may be multiple lines,
    all of them end with a newline.
    """

    # XXX: sanity check to make sure we have a sane combination of keys.

    maxOptLen = 0
    for opt in optList:
        optLen = len(opt.get('long', ''))
        if optLen:
            if opt.get('optType', None) == "parameter":
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
    seen = {}
    for opt in optList:
        if opt.get('short', None) in seen or opt.get('long', None) in seen:
            continue
        for x in opt.get('short', None), opt.get('long', None):
            if x is not None:
                seen[x] = 1

        optLines = []
        comma = " "
        if opt.get('short', None):
            short = "-%c" % (opt['short'],)
        else:
            short = ''

        if opt.get('long', None):
            long = opt['long']
            if opt.get("optType", None) == "parameter":
                long = long + '='

            long = "%-*s" % (maxOptLen, long)
            if short:
                comma = ","
        else:
            long = " " * (maxOptLen + len('--'))

        if opt.get('optType', None) == 'command':
            column1 = '    %s      ' % long
        else:
            column1 = "  %2s%c --%s  " % (short, comma, long)

        if opt.get('doc', ''):
            doc = opt['doc'].strip()
        else:
            doc = ''

        if (opt.get("optType", None) == "parameter") \
           and not (opt.get('default', None) is None):
            doc = "%s [default: %s]" % (doc, opt['default'])

        if (opt.get("optType", None) == "parameter") \
           and opt.get('dispatch', None) is not None:
            d = opt['dispatch']
            if isinstance(d, CoerceParameter) and d.doc:
                doc = "%s. %s" % (doc, d.doc)

        if doc:
            column2_l = text.wordWrap(doc, colWidth2)
        else:
            column2_l = ['']

        optLines.append("%s%s\n" % (column1, column2_l.pop(0)))

        for line in column2_l:
            optLines.append("%s%s\n" % (colFiller1, line))

        optChunks.append(''.join(optLines))

    return optChunks


def flagFunction(method, name=None):
    reqArgs = method.im_func.func_code.co_argcount
    if reqArgs > 2:
        raise UsageError('Invalid Option function for %s' %
                         (name or method.func_name))
    if reqArgs == 2:
        # argName = method.im_func.func_code.co_varnames[1]
        return 0
    return 1


def portCoerce(value):
    """
    Coerce a string value to an int port number, and checks the validity.
    """
    value = int(value)
    if value < 0 or value > 65535:
        raise ValueError("Port number not in range: %s" % (value,))
    return value
portCoerce.coerceDoc = "Must be an int between 0 and 65535."


