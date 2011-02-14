# -*- test-case-name: twisted.test.test_zshcomp -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Rebuild the completion functions for the currently active version of Twisted::
    $ python zshcomp.py -i

This module implements a zsh code generator which generates completion code for
commands that use twisted.python.usage. This is the stuff that makes pressing
Tab at the command line work.

Maintainer: Eric Mangold

To build completion functions for your own commands, and not Twisted commands,
then just do something like this::

    o = mymodule.MyOptions()
    f = file('_mycommand', 'w')
    Builder("mycommand", o, f).write()

Then all you have to do is place the generated file somewhere in your
C{$fpath}, and restart zsh. Note the "site-functions" directory in your
C{$fpath} where you may install 3rd-party completion functions (like the one
you're building). Call C{siteFunctionsPath} to locate this directory
programmatically.

SPECIAL CLASS VARIABLES. You may set these on your usage.Options subclass::

    zsh_altArgDescr
    zsh_multiUse
    zsh_mutuallyExclusive
    zsh_actions
    zsh_actionDescr
    zsh_extras

Here is what they mean (with examples)::

    zsh_altArgDescr = {"foo":"use this description for foo instead"}
        A dict mapping long option names to alternate descriptions.  When this
        variable is present, the descriptions contained here will override
        those descriptions provided in the optFlags and optParameters
        variables.

    zsh_multiUse = ["foo", "bar"]
        A sequence containing those long option names which may appear on the
        command line more than once. By default, options will only be completed
        one time.

    zsh_mutuallyExclusive = [("foo", "bar"), ("bar", "baz")]
        A sequence of sequences, with each sub-sequence containing those long
        option names that are mutually exclusive. That is, those options that
        cannot appear on the command line together.

    zsh_actions = {"foo":'_files -g "*.foo"', "bar":"(one two three)",
            "colors":"_values -s , 'colors to use' red green blue"}
        A dict mapping long option names to Zsh "actions". These actions
        define what will be completed as the argument to the given option.  By
        default, all files/dirs will be completed if no action is given.

        Callables may instead be given for the values in this dict. The
        callable should accept no arguments, and return a string that will be
        used as the zsh "action" in the same way as the literal strings in the
        examples above.

        As you can see in the example above. The "foo" option will have files
        that end in .foo completed when the user presses Tab. The "bar"
        option will have either of the strings "one", "two", or "three"
        completed when the user presses Tab.

        "colors" will allow multiple arguments to be completed, seperated by
        commas. The possible arguments are red, green, and blue. Examples::

            my_command --foo some-file.foo --colors=red,green
            my_command --colors=green
            my_command --colors=green,blue

        Actions may take many forms, and it is beyond the scope of this
        document to illustrate them all. Please refer to the documention for
        the Zsh _arguments function. zshcomp is basically a front-end to Zsh's
        _arguments completion function.

        That documentation is available on the zsh web site at this URL:
        U{http://zsh.sunsite.dk/Doc/Release/zsh_19.html#SEC124}

    zsh_actionDescr = {"logfile":"log file name", "random":"random seed"}
        A dict mapping long option names to a description for the corresponding
        zsh "action". These descriptions are show above the generated matches
        when the user is doing completions for this option.

        Normally Zsh does not show these descriptions unless you have
        "verbose" completion turned on. Turn on verbosity with this in your
        ~/.zshrc::

            zstyle ':completion:*' verbose yes
            zstyle ':completion:*:descriptions' format '%B%d%b'

    zsh_extras = [":file to read from:action", ":file to write to:action"]
        A sequence of extra arguments that will be passed verbatim to Zsh's
        _arguments completion function. The _arguments function does all the
        hard work of doing command line completions. You can see how zshcomp
        invokes the _arguments call by looking at the generated completion
        files that this module creates.

   *** NOTE ***

        You will need to use this variable to describe completions for normal
        command line arguments. That is, those arguments that are not
        associated with an option. That is, the arguments that are given to the
        parseArgs method of your usage.Options subclass.

        In the example above, the 1st non-option argument will be described as
        "file to read from" and completion options will be generated in
        accordance with the "action". (See above about zsh "actions") The
        2nd non-option argument will be described as "file to write to" and
        the action will be interpreted likewise.

        Things you can put here are all documented under the _arguments
        function here: U{http://zsh.sunsite.dk/Doc/Release/zsh_19.html#SEC124}

Zsh Notes:

To enable advanced completion add something like this to your ~/.zshrc::

    autoload -U compinit
    compinit

For some extra verbosity, and general niceness add these lines too::

    zstyle ':completion:*' verbose yes
    zstyle ':completion:*:descriptions' format '%B%d%b'
    zstyle ':completion:*:messages' format '%d'
    zstyle ':completion:*:warnings' format 'No matches for: %d'

Have fun!
"""
import itertools, sys, commands, os.path

from twisted.python import reflect, util, usage
from twisted.scripts.mktap import IServiceMaker

class MyOptions(usage.Options):
    """
    Options for this file
    """
    longdesc = ""
    synopsis = "Usage: python zshcomp.py [--install | -i] | <output directory>"
    optFlags = [["install", "i",
                 'Output files to the "installation" directory ' \
                 '(twisted/python/zsh in the currently active ' \
                 'Twisted package)']]
    optParameters = [["directory", "d", None,
                      "Output files to this directory"]]
    def postOptions(self):
        if self['install'] and self['directory']:
            raise usage.UsageError, "Can't have --install and " \
                                    "--directory at the same time"
        if not self['install'] and not self['directory']:
            raise usage.UsageError, "Not enough arguments"
        if self['directory'] and not os.path.isdir(self['directory']):
            raise usage.UsageError, "%s is not a directory" % self['directory']

class Builder:
    def __init__(self, cmd_name, options, file):
        """
        @type cmd_name: C{str}
        @param cmd_name: The name of the command

        @type options: C{twisted.usage.Options}
        @param options: The C{twisted.usage.Options} instance defined for
                        this command

        @type file: C{file}
        @param file: The C{file} to write the completion function to
        """

        self.cmd_name = cmd_name
        self.options = options
        self.file = file

    def write(self):
        """
        Write the completion function to the file given to __init__
        @return: C{None}
        """
        # by default, we just write out a single call to _arguments
        self.file.write('#compdef %s\n' % (self.cmd_name,))
        gen = ArgumentsGenerator(self.cmd_name, self.options, self.file)
        gen.write()

class SubcommandBuilder(Builder):
    """
    Use this builder for commands that have sub-commands. twisted.python.usage
    has the notion of sub-commands that are defined using an entirely seperate
    Options class.
    """
    interface = None
    subcmdLabel = None

    def write(self):
        """
        Write the completion function to the file given to __init__
        @return: C{None}
        """
        self.file.write('#compdef %s\n' % (self.cmd_name,))
        self.file.write('local _zsh_subcmds_array\n_zsh_subcmds_array=(\n')
        from twisted import plugin as newplugin
        plugins = newplugin.getPlugins(self.interface)

        for p in plugins:
            self.file.write('"%s:%s"\n' % (p.tapname, p.description))
        self.file.write(")\n\n")

        self.options.__class__.zsh_extras = ['*::subcmd:->subcmd']
        gen = ArgumentsGenerator(self.cmd_name, self.options, self.file)
        gen.write()

        self.file.write("""if (( CURRENT == 1 )); then
  _describe "%s" _zsh_subcmds_array && ret=0
fi
(( ret )) || return 0

service="$words[1]"

case $service in\n""" % (self.subcmdLabel,))

        plugins = newplugin.getPlugins(self.interface)
        for p in plugins:
            self.file.write(p.tapname + ")\n")
            gen = ArgumentsGenerator(p.tapname, p.options(), self.file)
            gen.write()
            self.file.write(";;\n")
        self.file.write("*) _message \"don't know how to" \
                        " complete $service\";;\nesac")

class MktapBuilder(SubcommandBuilder):
    """
    Builder for the mktap command
    """
    interface = IServiceMaker
    subcmdLabel = 'tap to build'

class TwistdBuilder(SubcommandBuilder):
    """
    Builder for the twistd command
    """
    interface = IServiceMaker
    subcmdLabel = 'service to run'

class ArgumentsGenerator:
    """
    Generate a call to the zsh _arguments completion function
    based on data in a usage.Options subclass
    """
    def __init__(self, cmd_name, options, file):
        """
        @type cmd_name: C{str}
        @param cmd_name: The name of the command

        @type options: C{twisted.usage.Options}
        @param options: The C{twisted.usage.Options} instance defined
                        for this command

        @type file: C{file}
        @param file: The C{file} to write the completion function to
        """
        self.cmd_name = cmd_name
        self.options = options
        self.file = file

        self.altArgDescr = {}
        self.actionDescr = {}
        self.multiUse = []
        self.mutuallyExclusive = []
        self.actions = {}
        self.extras = []

        aCL = reflect.accumulateClassList
        aCD = reflect.accumulateClassDict

        aCD(options.__class__, 'zsh_altArgDescr', self.altArgDescr)
        aCD(options.__class__, 'zsh_actionDescr', self.actionDescr)
        aCL(options.__class__, 'zsh_multiUse', self.multiUse)
        aCL(options.__class__, 'zsh_mutuallyExclusive',
            self.mutuallyExclusive)
        aCD(options.__class__, 'zsh_actions', self.actions)
        aCL(options.__class__, 'zsh_extras', self.extras)

        optFlags = []
        optParams = []

        aCL(options.__class__, 'optFlags', optFlags)
        aCL(options.__class__, 'optParameters', optParams)

        for i, optList in enumerate(optFlags):
            if len(optList) != 3:
                optFlags[i] = util.padTo(3, optList)

        for i, optList in enumerate(optParams):
            if len(optList) != 4:
                optParams[i] = util.padTo(4, optList)


        self.optFlags = optFlags
        self.optParams = optParams

        optParams_d = {}
        for optList in optParams:
            optParams_d[optList[0]] = optList[1:]
        self.optParams_d = optParams_d

        optFlags_d = {}
        for optList in optFlags:
            optFlags_d[optList[0]] = optList[1:]
        self.optFlags_d = optFlags_d

        optAll_d = {}
        optAll_d.update(optParams_d)
        optAll_d.update(optFlags_d)
        self.optAll_d = optAll_d

        self.addAdditionalOptions()

        # makes sure none of the zsh_ data structures reference option
        # names that don't exist. (great for catching typos)
        self.verifyZshNames()

        self.excludes = self.makeExcludesDict()

    def write(self):
        """
        Write the zsh completion code to the file given to __init__
        @return: C{None}
        """
        self.writeHeader()
        self.writeExtras()
        self.writeOptions()
        self.writeFooter()

    def writeHeader(self):
        """
        This is the start of the code that calls _arguments
        @return: C{None}
        """
        self.file.write('_arguments -s -A "-*" \\\n')

    def writeOptions(self):
        """
        Write out zsh code for each option in this command
        @return: C{None}
        """
        optNames = self.optAll_d.keys()
        optNames.sort()
        for long in optNames:
            self.writeOpt(long)

    def writeExtras(self):
        """
        Write out the "extras" list. These are just passed verbatim to the
        _arguments call
        @return: C{None}
        """
        for s in self.extras:
            self.file.write(escape(s))
            self.file.write(' \\\n')

    def writeFooter(self):
        """
        Write the last bit of code that finishes the call to _arguments
        @return: C{None}
        """
        self.file.write('&& return 0\n')

    def verifyZshNames(self):
        """
        Ensure that none of the names given in zsh_* variables are typoed
        @return: C{None}
        @raise ValueError: Raised if unknown option names have been given in
                           zsh_* variables
        """
        def err(name):
            raise ValueError, "Unknown option name \"%s\" found while\n" \
                "examining zsh_ attributes for the %s command" % (
                    name, self.cmd_name)

        for name in itertools.chain(self.altArgDescr, self.actionDescr,
        self.actions, self.multiUse):
            if name not in self.optAll_d:
                err(name)

        for seq in self.mutuallyExclusive:
            for name in seq:
                if name not in self.optAll_d:
                    err(name)

    def excludeStr(self, long, buildShort=False):
        """
        Generate an "exclusion string" for the given option

        @type long: C{str}
        @param long: The long name of the option
                     (i.e. "verbose" instead of "v")

        @type buildShort: C{bool}
        @param buildShort: May be True to indicate we're building an excludes
                           string for the short option that correspondes to
                           the given long opt

        @return: The generated C{str}
        """
        if long in self.excludes:
            exclusions = self.excludes[long][:]
        else:
            exclusions = []

        # if long isn't a multiUse option (can't appear on the cmd line more
        # than once), then we have to exclude the short option if we're
        # building for the long option, and vice versa.
        if long not in self.multiUse:
            if buildShort is False:
                short = self.getShortOption(long)
                if short is not None:
                    exclusions.append(short)
            else:
                exclusions.append(long)

        if not exclusions:
            return ''

        strings = []
        for optName in exclusions:
            if len(optName) == 1:
                # short option
                strings.append("-" + optName)
            else:
                strings.append("--" + optName)
        return "(%s)" % " ".join(strings)

    def makeExcludesDict(self):
        """
        @return: A C{dict} that maps each option name appearing in
        self.mutuallyExclusive to a list of those option names that
        is it mutually exclusive with (can't appear on the cmd line with)
        """

        #create a mapping of long option name -> single character name
        longToShort = {}
        for optList in itertools.chain(self.optParams, self.optFlags):
            try:
                if optList[1] != None:
                    longToShort[optList[0]] = optList[1]
            except IndexError:
                pass

        excludes = {}
        for lst in self.mutuallyExclusive:
            for i, long in enumerate(lst):
                tmp = []
                tmp.extend(lst[:i])
                tmp.extend(lst[i+1:])
                for name in tmp[:]:
                    if name in longToShort:
                        tmp.append(longToShort[name])

                if long in excludes:
                    excludes[long].extend(tmp)
                else:
                    excludes[long] = tmp
        return excludes

    def writeOpt(self, long):
        """
        Write out the zsh code for the given argument. This is just part of the
        one big call to _arguments

        @type long: C{str}
        @param long: The long name of the option
                     (i.e. "verbose" instead of "v")

        @return: C{None}
        """
        if long in self.optFlags_d:
            # It's a flag option. Not one that takes a parameter.
            long_field = "--%s" % long
        else:
            long_field = "--%s=" % long

        short = self.getShortOption(long)
        if short != None:
            short_field = "-" + short
        else:
            short_field = ''

        descr = self.getDescription(long)
        descr_field = descr.replace("[", "\[")
        descr_field = descr_field.replace("]", "\]")
        descr_field = '[%s]' % descr_field

        if long in self.actionDescr:
            actionDescr_field = self.actionDescr[long]
        else:
            actionDescr_field = descr

        action_field = self.getAction(long)
        if long in self.multiUse:
            multi_field = '*'
        else:
            multi_field = ''

        longExclusions_field = self.excludeStr(long)

        if short:
            #we have to write an extra line for the short option if we have one
            shortExclusions_field = self.excludeStr(long, buildShort=True)
            self.file.write(escape('%s%s%s%s%s' % (shortExclusions_field,
                multi_field, short_field, descr_field, action_field)))
            self.file.write(' \\\n')

        self.file.write(escape('%s%s%s%s%s' % (longExclusions_field,
            multi_field, long_field, descr_field, action_field)))
        self.file.write(' \\\n')

    def getAction(self, long):
        """
        Return a zsh "action" string for the given argument
        @return: C{str}
        """
        if long in self.actions:
            if callable(self.actions[long]):
                action = self.actions[long]()
            else:
                action = self.actions[long]
            return ":%s:%s" % (self.getActionDescr(long), action)
        if long in self.optParams_d:
            return ':%s:_files' % self.getActionDescr(long)
        return ''

    def getActionDescr(self, long):
        """
        Return the description to be used when this argument is completed
        @return: C{str}
        """
        if long in self.actionDescr:
            return self.actionDescr[long]
        else:
            return long

    def getDescription(self, long):
        """
        Return the description to be used for this argument
        @return: C{str}
        """
        #check if we have an alternate descr for this arg, and if so use it
        if long in self.altArgDescr:
            return self.altArgDescr[long]

        #otherwise we have to get it from the optFlags or optParams
        try:
            descr = self.optFlags_d[long][1]
        except KeyError:
            try:
                descr = self.optParams_d[long][2]
            except KeyError:
                descr = None

        if descr is not None:
            return descr

        # lets try to get it from the opt_foo method doc string if there is one
        longMangled = long.replace('-', '_') # this is what t.p.usage does
        obj = getattr(self.options, 'opt_%s' % longMangled, None)
        if obj:
            descr = descrFromDoc(obj)
            if descr is not None:
                return descr

        return long # we really ought to have a good description to use

    def getShortOption(self, long):
        """
        Return the short option letter or None
        @return: C{str} or C{None}
        """
        optList = self.optAll_d[long]
        try:
            return optList[0] or None
        except IndexError:
            pass

    def addAdditionalOptions(self):
        """
        Add additional options to the optFlags and optParams lists.
        These will be defined by 'opt_foo' methods of the Options subclass
        @return: C{None}
        """
        methodsDict = {}
        reflect.accumulateMethods(self.options, methodsDict, 'opt_')
        methodToShort = {}
        for name in methodsDict.copy():
            if len(name) == 1:
                methodToShort[methodsDict[name]] = name
                del methodsDict[name]

        for methodName, methodObj in methodsDict.items():
            long = methodName.replace('_', '-') # t.p.usage does this
            # if this option is already defined by the optFlags or
            # optParameters then we don't want to override that data
            if long in self.optAll_d:
                continue

            descr = self.getDescription(long)

            short = None
            if methodObj in methodToShort:
                short = methodToShort[methodObj]

            reqArgs = methodObj.im_func.func_code.co_argcount
            if reqArgs == 2:
                self.optParams.append([long, short, None, descr])
                self.optParams_d[long] = [short, None, descr]
                self.optAll_d[long] = [short, None, descr]
            elif reqArgs == 1:
                self.optFlags.append([long, short, descr])
                self.optFlags_d[long] = [short, descr]
                self.optAll_d[long] = [short, None, descr]
            else:
                raise TypeError, '%r has wrong number ' \
                                 'of arguments' % (methodObj,)

def descrFromDoc(obj):
    """
    Generate an appropriate description from docstring of the given object
    """
    if obj.__doc__ is None:
        return None

    lines = obj.__doc__.split("\n")
    descr = None
    try:
        if lines[0] != "" and not lines[0].isspace():
            descr = lines[0].lstrip()
        # skip first line if it's blank
        elif lines[1] != "" and not lines[1].isspace():
            descr = lines[1].lstrip()
    except IndexError:
        pass
    return descr

def firstLine(s):
    """
    Return the first line of the given string
    """
    try:
        i = s.index('\n')
        return s[:i]
    except ValueError:
        return s

def escape(str):
    """
    Shell escape the given string
    """
    return commands.mkarg(str)[1:]

def siteFunctionsPath():
    """
    Return the path to the system-wide site-functions directory or
    C{None} if it cannot be determined
    """
    try:
        cmd = "zsh -f -c 'echo ${(M)fpath:#/*/site-functions}'"
        output = commands.getoutput(cmd)
        if os.path.isdir(output):
            return output
    except:
        pass

generateFor = [('conch', 'twisted.conch.scripts.conch', 'ClientOptions'),
               ('mktap', 'twisted.scripts.mktap', 'FirstPassOptions'),
               ('trial', 'twisted.scripts.trial', 'Options'),
               ('cftp', 'twisted.conch.scripts.cftp', 'ClientOptions'),
               ('tapconvert', 'twisted.scripts.tapconvert', 'ConvertOptions'),
               ('twistd', 'twisted.scripts.twistd', 'ServerOptions'),
               ('ckeygen', 'twisted.conch.scripts.ckeygen', 'GeneralOptions'),
               ('lore', 'twisted.lore.scripts.lore', 'Options'),
               ('pyhtmlizer', 'twisted.scripts.htmlizer', 'Options'),
               ('tap2deb', 'twisted.scripts.tap2deb', 'MyOptions'),
               ('tkconch', 'twisted.conch.scripts.tkconch', 'GeneralOptions'),
               ('manhole', 'twisted.scripts.manhole', 'MyOptions'),
               ('tap2rpm', 'twisted.scripts.tap2rpm', 'MyOptions'),
               ('websetroot', None, None),
               ('tkmktap', None, None),
               ]
# NOTE: the commands using None above are no longer included in Twisted.
# However due to limitations in zsh's completion system the version of
# _twisted_zsh_stub shipped with zsh contains a static list of Twisted's
# commands. It will display errors if completion functions for these missing
# commands are not found :( So we just include dummy (empty) completion
# function files

specialBuilders = {'mktap'  : MktapBuilder,
                   'twistd' : TwistdBuilder}

def makeCompFunctionFiles(out_path, generateFor=generateFor,
                          specialBuilders=specialBuilders):
    """
    Generate completion function files in the given directory for all
    twisted commands

    @type out_path: C{str}
    @param out_path: The path to the directory to generate completion function
                     fils in

    @param generateFor: Sequence in the form of the 'generateFor' top-level
                        variable as defined in this module. Indicates what
                        commands to build completion files for.

    @param specialBuilders: Sequence in the form of the 'specialBuilders'
                            top-level variable as defined in this module.
                            Indicates what commands require a special
                            Builder class.

    @return: C{list} of 2-tuples of the form (cmd_name, error) indicating
             commands that we skipped building completions for. cmd_name
             is the name of the skipped command, and error is the Exception
             that was raised when trying to import the script module.
             Commands are usually skipped due to a missing dependency,
             e.g. Tkinter.
    """
    skips = []
    for cmd_name, module_name, class_name in generateFor:
        if module_name is None:
            # create empty file
            f = _openCmdFile(out_path, cmd_name)
            f.close()
            continue
        try:
            m = __import__('%s' % (module_name,), None, None, (class_name))
            f = _openCmdFile(out_path, cmd_name)
            o = getattr(m, class_name)() # instantiate Options class

            if cmd_name in specialBuilders:
                b = specialBuilders[cmd_name](cmd_name, o, f)
                b.write()
            else:
                b = Builder(cmd_name, o, f)
                b.write()
        except Exception, e:
            skips.append( (cmd_name, e) )
            continue
    return skips

def _openCmdFile(out_path, cmd_name):
    return file(os.path.join(out_path, '_'+cmd_name), 'w')

def run():
    options = MyOptions()
    try:
        options.parseOptions(sys.argv[1:])
    except usage.UsageError, e:
        print e
        print options.getUsage()
        sys.exit(2)

    if options['install']:
        import twisted
        dir = os.path.join(os.path.dirname(twisted.__file__), "python", "zsh")
        skips = makeCompFunctionFiles(dir)
    else:
        skips = makeCompFunctionFiles(options['directory'])

    for cmd_name, error in skips:
        sys.stderr.write("zshcomp: Skipped building for %s. Script module " \
                         "could not be imported:\n" % (cmd_name,))
        sys.stderr.write(str(error)+'\n')
    if skips:
        sys.exit(3)

if __name__ == '__main__':
    run()
