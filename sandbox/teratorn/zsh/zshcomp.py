"""
This module implements a zsh code generator which generates completion code
for commands that use twisted.python.usage. This is the stuff that makes
pressing Tab at the command line work.
"""

# the list of commands to generate zsh completion code for. and the name of the usage.Option's subclass
# we should use for generation
generateFor = [('conch', 'GeneralOptions')]

import sys, commands
from twisted import scripts

def escape(str):
    return commands.mkarg(str)[1:]

def makeZshCode(cmd_name, optionsClass, out_file):
    """write the zsh completion code to the given file"""
    o = optionsClass()
    optParameters = getattr(o, 'optParameters', None)
    optFlags = getattr(o, 'optFlags', None)
    out_file.write('#compdef %s\n' % cmd_name)
    out_file.write('_arguments \\\n')

    if optParameters:
        for optList in optParameters:
            long, short, default = optList[:3]
            length = len(optList)
            if length == 3:
                descr = getattr(o, 'opt_%s' % optList[0]).__doc__
            elif length == 4:
                descr = optList[3]
            else:
                raise SystemExit, 'len(optList) == %s' % len(optList)

            longExclusion = ''

            action = o.zshComps.get(long)
            if action == None:
                action = ' '

            if short:
                out_file.write(escape('(--%s)-%s[%s]:%s:%s' % (long, short, descr, long, action)))
                out_file.write(' \\\n')
                longExclusion = '(-%s)' % short
            out_file.write(escape('%s--%s=[%s]:%s:%s' % (longExclusion, long, descr, long, action)))
            out_file.write(' \\\n')

    if optFlags:
        for optList in optFlags:
            long, short, descr = optList
            longExclusion = ''
            if short:
                escape('(--%s)-%s[%s]' % (long, short, descr))
                longExclusion = '(-%s)' % short
            out_file.write(escape('%s-%s[%s]' % (longExclusion, long, descr)))
            out_file.write(' \\\n')

    out_file.write('&& return 0\n')

def makeCompFunctionFiles(out_path):
    for cmd_name, class_name in generateFor:
        # I hope this is a correct usage of __import__
        m = __import__('twisted.scripts.%s' % cmd_name, None, None, (class_name))
        o = getattr(m, class_name)
        f = file('%s/_%s' % (out_path, cmd_name), 'w')
        makeZshCode(cmd_name, o, f)

def run():
    if len(sys.argv) != 2:
        print 'Usage: python zshcomp.py <output directory>\n \
    where <output directory> is the path to write\n \
    the completion function files to.'
        sys.exit(1)
    makeCompFunctionFiles(sys.argv[1])

if __name__ == '__main__':
    run()

