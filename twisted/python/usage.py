
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

    from twisted import usage
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
import sys
import getopt
import types

# Sibling Imports
import reflect

error = getopt.error

class Options:
    """
    A class which can be subclassed to provide command-line options to your
    program. See twisted.usage.__doc__ for for details.
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

        for long, short in flags:
            setattr(self, long, 0)
            if short:
                shortOpt = shortOpt + short
            longOpt.append(long)
            flagDict[short] = long
            flagDict[long] = long

        for long, short, default in strings:
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
        """ TODO: Undocumented """
        pass

    def parseArgs(self):
        """ TODO: Undocumented """
        pass
