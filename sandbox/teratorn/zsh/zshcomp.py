"""
This module implements a zsh code generator which generates completion code
for commands that use twisted.python.usage. This is the stuff that makes
pressing Tab at the command line work.
"""

# the list of commands to generate zsh completion code for. and the name of the usage.Option's subclass
# we should use for generation
generateFor = [('twistd', 'ServerOptions')]

import sys, commands
from twisted import scripts
from twisted.python import reflect

def escape(str):
    return commands.mkarg(str)[1:]

class writeZshCode:
    def __init__(self, cmd_name, optionsClass, file):
        """write the zsh completion code to the given file"""
        self.cmd_name = cmd_name
        self.optionsClass = optionsClass
        self.file = file

        self.optParams = getattr(optionsClass, 'optParameters', [])
        self.optFlags = getattr(optionsClass, 'optFlags', [])
        self.altArgDescr = getattr(optionsClass, 'zsh_altArgDescr', {})
        self.multiUse = getattr(optionsClass, 'zsh_multiUse', [])
        self.actions = getattr(optionsClass, 'zsh_actions', {})

        self.writeHeader()

        self.addAdditionalOptions()
        self.writeOptParamLines()
        self.writeOptFlagLines()

        self.writeFooter()

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
                descr = '[%s]' % optList[3]
            else:
                raise SystemExit, 'optList has invalid length'

            if long in self.altArgDescr:
                descr = '[%s]' % self.altArgDescr[long]
            else:
                if descr == None:
                    descr = ''

            longExclude = ''
            shortExclude = ''
            multi = ''
            #shortExclude = '(-%s)' % short
            action = self.actions.get(long, ' ')
            if short:
                if long in self.multiUse:
                    multi = '*'
                else:
                    longExclude = '(--%s)' % long
                    shortExclude = '(-%s)' % short

                self.file.write(escape('%s%s-%s%s:%s:%s' % (longExclude, multi, short, descr, long, action)))
                self.file.write(' \\\n')

            self.file.write(escape('%s%s--%s=%s:%s:%s' % (shortExclude, multi, long, descr, long, action)))
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

            longExclude = ''
            shortExclude = ''
            multi = ''
            if short:
                if long in self.multiUse:
                    multi = '*'
                else:
                    longExclude = '(--%s)' % long
                    shortExclude = '(-%s)' % short

                self.file.write(escape('%s%s-%s%s' % (longExclude, multi, short, descr)))
                self.file.write(' \\\n')

            self.file.write(escape('%s%s--%s%s' % (shortExclude, multi, long, descr)))
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

def firstLine(s):
    try:
        i = s.find('\n')
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
        writeZshCode(cmd_name, o, f)

def run():
    if len(sys.argv) != 2:
        print 'Usage: python zshcomp.py <output directory>\n \
    where <output directory> is the path to write\n \
    the completion function files to.'
        sys.exit(1)
    makeCompFunctionFiles(sys.argv[1])

if __name__ == '__main__':
    run()

