"""
This module implements a zsh code generator which generates completion code
for commands that use twisted.python.usage. This is the stuff that makes
pressing Tab at the command line work.
"""
import sys, commands, itertools
from twisted.python import reflect, util

# commands to generate completion function files for
generateFor = [
               ('trial', 'twisted.scripts.trial', 'Options'),
               ('conch', 'twisted.conch.scripts.conch', 'ClientOptions'),
               ('mktap', 'twisted.scripts.mktap', 'FirstPassOptions'),
               ('cftp', 'twisted.conch.scripts.cftp', 'ClientOptions'),
               ('tapconvert', 'twisted.scripts.tapconvert', 'ConvertOptions'),
               ('twistd', 'twisted.scripts.twistd', 'ServerOptions'),
               ('ckeygen', 'twisted.conch.scripts.ckeygen', 'GeneralOptions'),
               ('lore', 'twisted.lore.scripts.lore', 'Options'),
               ('pyhtmlizer', 'twisted.scripts.htmlizer', 'Options'),
               ('websetroot', 'twisted.web.scripts.websetroot', 'Options'),
               ('tap2deb', 'twisted.scripts.tap2deb', 'MyOptions'),
               ('tkmktap', 'twisted.scripts.tap2deb', 'MyOptions'),
               ('tkconch', 'twisted.conch.scripts.tkconch', 'GeneralOptions'),
               ('manhole', 'twisted.scripts.manhole', 'MyOptions'),
               ('tap2rpm', 'twisted.scripts.tap2rpm', 'MyOptions'),
               ]
#for l in generateFor:
#    import sys
#    sys.stdout.write(l[0] + " ")

# these attributes may be set on usage.Option subclasses to further
# refine how command completion is handled

    #zsh_altArgDescr = {"foo":"use this description for foo instead"}
    #zsh_multiUse = ["foo", "bar"]
    #zsh_mutuallyExclusive = [("foo", "bar"), ("bar", "baz")]
    #zsh_actions = {"foo":'_files -g "*.foo"', "bar":"(one two three)"}
    #zsh_actionDescr = {"logfile":"log file name", "random":"random seed"}

class zshCodeGenerator:
    def __init__(self, cmd_name, optionsClass, file):
        """write the zsh completion code to the given file"""
        self.cmd_name = cmd_name
        self.optionsClass = optionsClass
        self.file = file

        self.altArgDescr = {}
        self.actionDescr = {}
        self.multiUse = []
        self.mutuallyExclusive = []
        self.actions = {}

        aCL = reflect.accumulateClassList
        aCD = reflect.accumulateClassDict

        aCD(optionsClass, 'zsh_altArgDescr', self.altArgDescr)
        aCD(optionsClass, 'zsh_actionDescr', self.actionDescr)
        aCL(optionsClass, 'zsh_multiUse', self.multiUse)
        aCL(optionsClass, 'zsh_mutuallyExclusive', self.mutuallyExclusive)
        aCD(optionsClass, 'zsh_actions', self.actions)

        optFlags = []
        optParams = []

        aCL(optionsClass, 'optFlags', optFlags)
#        optFlags = getattr(optionsClass, 'optFlags', [])
        aCL(optionsClass, 'optParameters', optParams)
#        optParams = getattr(optionsClass, 'optParameters', [])

#        for l in optFlags:
#            print l
#        for l in optParams:
#            print l

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

        # makes sure none of the zsh_ data structures reference option names that
        # don't exist. (great for catching typos)
        self.verifyZshNames()
        
        self.excludes = self.makeExcludesDict()

    def verifyZshNames(self):
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
        """buildShort may be True to indicate we're building an excludes
        string for the short option that correspondes to the given long opt"""
        if long in self.excludes:
            exclusions = self.excludes[long][:]
        else:
            exclusions = []

        # if we aren't a multiUse option (can't appear on the cmd line more
        # than once), then we have to exclude the short option if we're
        # building for the long option, and vice versa.
        if long not in self.multiUse:
            if buildShort is False:
                short = self.optAll_d[long][0] 
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

    def writeStandardFunction(self):
        self.writeHeader()

        for optList in itertools.chain(self.optFlags, self.optParams):
            self.writeOption(optList[0])

        self.writeFooter()

    def makeExcludesDict(self):
        """return a dict that maps each option name appearing in
        self.mutuallyExclusive to a list of those option names that
        is it mutually exclusive with (can't appear on the cmd line with)"""

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

    def writeHeader(self):
        self.file.write('#compdef %s\n' % self.cmd_name)
        self.file.write('_arguments -s \\\n')

    def writeFooter(self):
        self.file.write('&& return 0\n')

    def writeOption(self, long):
        if long in self.optFlags_d: # It's a flag option. Not one that takes a parameter.
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

        #longExclude_field, shortExclude_field = self.makeExcludeStrings(long, short)
        action_field = self.getAction(long)
        if long in self.multiUse:
            multi_field = '*'
        else:
            multi_field = ''

        longExclusions_field = self.excludeStr(long)

        if short:
            #we have to write an extra line for the short option if we have one
            shortExclusions_field = self.excludeStr(long, buildShort=True)
            self.file.write(escape('%s%s%s%s%s' %
                (shortExclusions_field, multi_field, short_field, descr_field, action_field)))
            self.file.write(' \\\n')

        self.file.write(escape('%s%s%s%s%s' %
            (longExclusions_field, multi_field, long_field, descr_field, action_field)))
        self.file.write(' \\\n')

    def getAction(self, long):
        if long in self.actions:
            return ":%s:%s" % (self.getActionDescr(long), self.actions[long])
        if long in self.optParams_d:
            return ':%s:_files' % self.getActionDescr(long)
        return ''

    def getActionDescr(self, long):
        if long in self.actionDescr:
            return self.actionDescr[long]
        else:
            return long

    def getDescription(self, long):
        """Return the description to be used for this long argument"""
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

        # lets try to get it from the opt_foo method doc string, if there is one
        longMangled = long.replace('-', '_') # this is what t.p.usage does
        obj = getattr(self.optionsClass, 'opt_%s' % longMangled, None)
        if obj:
            descr = self.descrFromDoc(obj)
            if descr is not None:
                return descr

        return long # we really ought to have a good description to use


    def getShortOption(self, long):
        """Return the short option letter or None"""
        optList = self.optAll_d[long]
        try:
            return optList[0]
        except IndexError:
            pass

    def addAdditionalOptions(self):
        """Add additional options to the optFlags and optParams lists.
        These will be defined by 'opt_foo' methods of the Options subclass"""
        methodsDict = {}
        reflect.accumulateMethods(self.optionsClass, methodsDict, 'opt_', curClass=self.optionsClass)
        # we need to go through methodsDict and figure out is there are such things as
        # opt_debug and opt_b that point to the same method (long and short option names
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
                raise SystemExit, 'opt_ method has wrong number of arguments'

    def descrFromDoc(self, obj):
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
    try:
        i = s.index('\n')
        return s[:i]
    except ValueError:
        return s

def escape(str):
    return commands.mkarg(str)[1:]

def makeCompFunctionFiles(out_path):
    for cmd_name, module_name, class_name in generateFor:
        m = __import__('%s' % module_name, None, None, (class_name))
        o = getattr(m, class_name)
        f = file('%s/_%s' % (out_path, cmd_name), 'w')
        z = zshCodeGenerator(cmd_name, o, f)
        z.writeStandardFunction()

def run():
    if len(sys.argv) != 2:
        print "Usage: python zshcomp.py <output directory>\n" \
        "       python zshcomp.py -d\n" \
        "where <output directory> is the path to write\n" \
        "the completion function files to. Or specify -d to use\n" \
        "the defualt output dir. (.../twisted/python/zsh of the\n" \
        "current Twisted installation"
        sys.exit(1)

    if sys.argv[1] == '-d':
        import twisted, os.path
        dir = os.path.dirname(twisted.__file__) + os.path.sep + os.path.join("python", "zsh")
        makeCompFunctionFiles(dir)
    else:
        makeCompFunctionFiles(sys.argv[1])


if __name__ == '__main__':
    run()


