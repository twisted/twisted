
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
#
# $Id: mktap.py,v 1.19 2002/09/08 02:23:11 exarkun Exp $

""" Implementation module for the `mktap` command.
"""

from twisted.protocols import telnet
from twisted.internet import app
from twisted.python import usage, util
from twisted.spread import pb

import sys, traceback, os, cPickle, glob, string

from twisted.python.plugin import getPlugIns


# !!! This code makes it hard to NOT run it as top-level code;
# should be refactored; also, I bet that it shares a lot with
# other scripts (i.e. is badly cut'n'pasted).

try:
    plugins = getPlugIns("tap")
except IOError:
    print "Couldn't load the plugins file!"
    sys.exit(2)

tapLookup = {}
for plug in plugins:
    if hasattr(plug, 'tapname'):
        shortTapName = plug.tapname
    else:
        shortTapName = string.split(plug.module, '.')[-1]
    tapLookup[shortTapName] = plug

tapMods = tapLookup.keys()

def findAGoodName(x): return getattr(x, 'tapname', getattr(x, 'name', getattr(x, 'module')))

def getModule(type):
    try:
        mod = tapLookup[type].load()
        return mod
    except KeyError:
        print """Please select one of: %s""" % string.join(tapMods)
        sys.exit(2)

class GeneralOptions(usage.Options):
    synopsis = """Usage:    mktap [options] <command> [command options]
 """

    optParameters = [['uid', 'u', '0'],
                  ['gid', 'g', '0'],
                  ['append', 'a', None, "An existing .tap file to append the plugin to, rather than creating a new one."],
                  ['type', 't', 'pickle', "The output format to use; this can be 'pickle', 'xml', or 'source'."]]
    optFlags = [['xml', 'x', "DEPRECATED: same as --type=xml"],
                ['source', 's', "DEPRECATED: same as --type=source"],
                ['encrypted', 'e', "Encrypt file before writing"]]

    subCommands = [
        [x, None, (lambda obj = y: obj.load().Options()), getattr(y, 'description', '')] for (x, y) in tapLookup.items()
    ]
    subCommands.sort()

    def __init__(self):
        usage.Options.__init__(self)
        self['help'] = 0 # default

    def opt_help(self):
        """display this message"""
        # Ugh, we can't print the help now, we need to let getopt
        # finish parsinsg and parseArgs to run.
        self['help'] = 1

    def parseArgs(self, *args):
        self.args = args


# Rest of code in "run"

def run():
    options = GeneralOptions()
    if hasattr(os, 'getgid'):
        options['uid'] = os.getuid()
        options['gid'] = os.getgid()
    try:
        options.parseOptions(sys.argv[1:])
    except Exception, e:
        # XXX: While developing, I find myself frequently disabling
        # this except block when I want to see what screwed up code
        # caused my updateApplication crash.  That probably means
        # we're not doing something right here.  - KMT

        if isinstance(e, SystemExit):
            # We don't really want to catch this at all...
            raise
        print str(sys.exc_value)
        print str(options)
        sys.exit(2)

    if options['help'] or not hasattr(options, 'subOptions'):
        if hasattr(options, 'subOptions'):
            options.subOptions.opt_help()
        usage.Options.opt_help(options)
        sys.exit()

    mod = getModule(options.subCommand)
    if not options['append']:
        a = app.Application(options.subCommand, int(options['uid']), int(options['gid']))
    else:
        a = cPickle.load(open(options['append'], 'rb'))

    try:
        mod.updateApplication(a, options.subOptions)
    except usage.error, ue:
        print "Usage Error: %s" % ue
        options.subOptions.opt_help()
        sys.exit(1)

    # backwards compatible interface
    if hasattr(mod, "getPorts"):
        print "The use of getPorts() is deprecated."
        for portno, factory in mod.getPorts():
            a.listenTCP(portno, factory)

    #backwards compatibility for old --xml and --source options
    if options['xml']:
        options['type'] = 'xml'
    if options['source']:
        options['type'] = 'source'

    a.persistStyle = ({'xml': 'xml',
                       'source': 'aot',
                       'pickle': 'pickle'}
                       [options['type']])
    if options['encrypted']:
        try:
            import Crypto
            a.save(passphrase=util.getPassword("Encryption passphrase: "))
        except ImportError:
            print "The --encrypt flag requires the PyCrypto module, no file written."
    else:
        a.save()

# Make it script-callable for testing purposes
if __name__ == "__main__":
    run()
