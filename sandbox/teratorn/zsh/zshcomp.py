"""
This module implements a zsh code generator which generates completion code
for commands that use twisted.python.usage. This is the stuff that makes
pressing Tab at the command line work.
"""

# the list of commands to generate zsh completion code for. and the name of the usage.Option's subclass
# we should use for generation
generateFor = [('twistd', 'ServerOptions')]

import sys, commands, itertools
from twisted import scripts
from twisted.python import reflect

def escape(str):
    return commands.mkarg(str)[1:]

class zshCodeWriter:
    def __init__(self, cmd_name, optionsClass, file):
        """write the zsh completion code to the given file"""
        self.cmd_name = cmd_name
        self.optionsClass = optionsClass
        self.file = file

        self.optParams = getattr(optionsClass, 'optParameters', [])
        self.optFlags = getattr(optionsClass, 'optFlags', [])
        self.altArgDescr = getattr(optionsClass, 'zsh_altArgDescr', {})
        self.multiUse = getattr(optionsClass, 'zsh_multiUse', [])
        self.mutuallyExclusive = getattr(optionsClass, 'zsh_mutuallyExclusive', [])
        self.actions = getattr(optionsClass, 'zsh_actions', {})

        self.excludes = self.makeExcludesDict() 

        self.addAdditionalOptions()

    def writeStandardFunction(self)
        self.writeHeader()

        self.writeOptParamLines()
        self.writeOptFlagLines()

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

                if lst[i] in excludes:
                    excludes[lst[i]].extend(tmp)
                else:
                    excludes[lst[i]] = tmp

        return excludes

    def makeExcludeStrings(self, long, short):
        excludeList = self.excludes.get(long, [])
        if short and long not in self.multiUse:
            longExcludes = excludeList + [short]
            shortExcludes = excludeList + [long]
        else:
            longExcludes = excludeList
            shortExcludes = excludeList
        
        return excludeString(longExcludes), excludeString(shortExcludes)

    def writeHeader(self):
        self.file.write('#compdef %s\n' % self.cmd_name)
        self.file.write('_arguments \\\n')

    def writeFooter(self):
        self.file.write('&& return 0\n')

    def writeOptParamLines(self):
        for optList in self.optParams:
            length = len(optList)
            if length == 1:
                long = optList[0]
                short, descr = None, None
            elif length == 2 or length == 3:
                long, short = optList
                descr = None
            elif length == 4:
                long, short = optList[:2]
                descr = '[%s]' % firstLine(optList[3])
            else:
                raise SystemExit, 'optList has invalid length'

            if long in self.altArgDescr:
                descr = '[%s]' % self.altArgDescr[long]
            else:
                if descr == None:
                    descr = ''

            action = self.actions.get(long, ' ')

            longExcludeStr, shortExcludeStr = self.makeExcludeStrings(long, short)
            multi = ''
            if short:
                if long in self.multiUse:
                    multi = '*'
                self.file.write(escape('%s%s-%s%s:%s:%s' %
                                      (shortExcludeStr, multi, short, descr, long, action)))
                self.file.write(' \\\n')

            self.file.write(escape('%s%s--%s=%s:%s:%s' %
                                  (longExcludeStr, multi, long, descr, long, action)))
            self.file.write(' \\\n')

    def writeOptFlagLines(self):
        for optList in self.optFlags:
            length = len(optList)
            if length == 1:
                long = optList[0]
                short, descr = None, None
            elif length == 2:
                long, short = optList
                descr = None
            elif length == 3:
                long, short = optList[:2]
                descr = '[%s]' % firstLine(optList[2])
            else:
                raise SystemExit, 'optList has invalid length'

            if long in self.altArgDescr:
                descr = '[%s]' % altArgDescr[long]
            else:
                if descr == None:
                    descr = ''

            longExcludeStr, shortExcludeStr = self.makeExcludeStrings(long, short)
            multi = ''
            if short:
                if long in self.multiUse:
                    multi = '*'
                self.file.write(escape('%s%s-%s%s' %
                                      (shortExcludeStr, multi, short, descr)))
                self.file.write(' \\\n')

            self.file.write(escape('%s%s--%s%s' %
                                  (longExcludeStr, multi, long, descr)))
            self.file.write(' \\\n')

    def addAdditionalOptions(self):
        """Add additional options to the optFlags and optParams lists.
        These will be defined by 'opt_foo' methods of the Options subclass"""
        methodsDict = {}
        reflect.accumulateMethods(self.optionsClass, methodsDict, 'opt_')
        for methodName, methodObj in methodsDict.items():
            if methodName in self.altArgDescr:
                descr = self.altArgDescr[methodName]
            else:
                descr = methodObj.__doc__

            reqArgs = methodObj.im_func.func_code.co_argcount
            if reqArgs == 2:
                self.optParams.append([methodName, None, None, descr])
            elif reqArgs == 1:
                self.optFlags.append([methodName, None, descr])
            else:
                raise SystemExit, 'opt_ method has wrong number of arguments'

def prependHyphens(s):
    """character options get one dash. word options get two."""
    if len(s) == 1: return '-%s' % s
    else: return '--%s' % s

def excludeString(seq):
    """take a list of option names and return a zsh exclusion list string"""
    if seq:
        return '(%s)' % ' '.join(map(prependHyphens, seq))
    else:
        return ''

def firstLine(s):
    try:
        i = s.index('\n')
        return s[:i]
    except ValueError:
        return s

def makeCompFunctionFiles(out_path):
    for cmd_name, class_name in generateFor:
        # I hope this is a correct usage of __import__
        #m = __import__('twisted.scripts.%s' % cmd_name, None, None, (class_name))
        #this is just for testing
        m = __import__('%s' % cmd_name, None, None, (class_name))
        o = getattr(m, class_name)
        f = file('%s/_%s' % (out_path, cmd_name), 'w')
        z = zshCodeWriter(cmd_name, o, f)
        z.writeStandardFunction()

def run():
    if len(sys.argv) != 2:
        print 'Usage: python zshcomp.py <output directory>\n \
    where <output directory> is the path to write\n \
    the completion function files to.'
        sys.exit(1)
    makeCompFunctionFiles(sys.argv[1])

if __name__ == '__main__':
    run()

