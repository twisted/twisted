
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
# $Id: mktap.py,v 1.9 2002/05/04 23:47:45 glyph Exp $

""" Implementation module for the `mktap` command.
"""
## Copied from bin/mktap 1.26!

from twisted.internet import default
default.install()
from twisted.protocols import telnet
from twisted.internet import app, tcp
from twisted.python import usage
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

class GeneralOptions(usage.Options):
    synopsis="""\
Usage::

  mktap 'apptype' [application_options]
  mktap --help 'apptype'

'apptype' can be one of: %s
""" % string.join(tapMods)

    optStrings = [['uid', 'u', '0'],
                  ['gid', 'g', '0'],
                  ['append', 'a', None]]
    help = 0

    def opt_help(self):
        """display this message"""
        # Ugh, we can't print the help now, we need to let getopt
        # finish parsinsg and parseArgs to run.
        self.help = 1

    def parseArgs(self, *args):
        self.args = args


def getModule(type):
    try:
        mod = tapLookup[type].load()
        return mod
    except KeyError:
        print """Please select one of: %s""" % string.join(tapMods)
        sys.exit(2)

# Rest of code in "run"

def run():
    options = GeneralOptions()
    if hasattr(os, 'getgid'):
        options.opts['uid'] = os.getuid()
        options.opts['gid'] = os.getgid()
    try:
        options.parseOptions(sys.argv[1:])
    except:
        print str(sys.exc_value)
        print str(options)
        sys.exit(2)

    if options.help or not options.args:
        if options.args:
            mod = getModule(options.args[0])
            config = mod.Options()
            config.opt_help()
            sys.exit()
        else:
            usage.Options.opt_help(options)
            sys.exit()
    else:
        mod = getModule(options.args[0])
    try:
        config = mod.Options()
        config.parseOptions(options.args[1:])
    except usage.error, ue:
        print "Usage Error: %s" % ue
        config.opt_help()
        sys.exit(1)

    if not options.opts['append']:
        a = app.Application(options.args[0], int(options.opts['uid']), int(options.opts['gid']))
    else:
        a = cPickle.load(open(options.opts['append']))

    try:
        mod.updateApplication(a, config)
    except usage.error, ue:
        print "Usage Error: %s" % ue
        config.opt_help()
        sys.exit(1)

    # backwards compatible interface
    if hasattr(mod, "getPorts"):
        print "The use of getPorts() is deprecated."
        for portno, factory in mod.getPorts():
            a.listenTCP(portno, factory)

    a.save()

# Make it script-callable for testing purposes
if __name__ == "__main__":
    run()

