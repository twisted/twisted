
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
# $Id: mktap.py,v 1.33 2003/04/11 16:56:18 exarkun Exp $

""" Implementation module for the `mktap` command.
"""

from twisted.protocols import telnet
from twisted.internet import app
from twisted.python import usage, util
from twisted.spread import pb

import sys, traceback, os, cPickle, glob, operator
try:
    import pwd
except ImportError:
    pwd = None
try:
    import grp
except ImportError:
    grp = None


from twisted.python.plugin import getPlugIns
from twisted.python import log

# !!! This code should be refactored; also,
# I bet that it shares a lot with other scripts
# (i.e. is badly cut'n'pasted).

def findAGoodName(x):
    return getattr(x, 'tapname', getattr(x, 'name', getattr(x, 'module')))

def loadPlugins(debug = None, progress = None):
    try:
        plugins = getPlugIns("tap", debug, progress)
    except IOError:
        print "Couldn't load the plugins file!"
        sys.exit(2)

    tapLookup = {}
    for plug in plugins:
        if hasattr(plug, 'tapname'):
            shortTapName = plug.tapname
        else:
            shortTapName = plug.module.split('.')[-1]
        tapLookup[shortTapName] = plug

    return tapLookup


def getModule(tapLookup, type):
    try:
        mod = tapLookup[type].load()
        return mod
    except KeyError:
        print """Please select one of: %s""" % ' '.join(tapLookup.keys())
        sys.exit(2)

class GeneralOptions:
    synopsis = """Usage:    mktap [options] <command> [command options] """

    uid = gid = None
    if hasattr(os, 'getgid'):
        uid, gid = os.getuid(), os.getgid()
    optParameters = [
        ['uid', 'u', uid, "The uid to run as."],
        ['gid', 'g', gid, "The gid to run as."],
        ['append', 'a', None,   "An existing .tap file to append the plugin to, rather than creating a new one."],
        ['type', 't', 'pickle', "The output format to use; this can be 'pickle', 'xml', or 'source'."],
        ['appname', 'n', None, "The process name to use for this application."]
    ]
    del uid, gid

    optFlags = [
        ['xml', 'x',       "DEPRECATED: same as --type=xml"],
        ['source', 's',    "DEPRECATED: same as --type=source"],
        ['encrypted', 'e', "Encrypt file before writing (will make the extension of the resultant file begin with 'e')"],
        
        ['debug', 'd',     "Show debug information for plugin loading"],
        ['progress', 'p',  "Show progress information for plugin loading"],
    ]

    def init(self, tapLookup):
        self.subCommands = []
        for (x, y) in tapLookup.items():
            self.subCommands.append(
                [x, None, (lambda obj = y: obj.load().Options()), getattr(y, 'description', '')]
             )
        self.subCommands.sort()
        self['help'] = 0 # default

    def postOptions(self):
        # backwards compatibility for old --xml and --source options
        if self['xml']:
            self['type'] = 'xml'
        if self['source']:
            self['type'] = 'source'

    def opt_help(self):
        """Display this message"""
        self['help'] = 1
    opt_h = opt_help

    def parseArgs(self, *args):
        self.args = args

class FirstPassOptions(usage.Options, GeneralOptions):
    def __init__(self):
        usage.Options.__init__(self)
        self['help'] = 0
        self.params = []
        self.recursing = 0
    
    def opt_help(self):
        """Display this message"""
        self['help'] = 1
    opt_h = opt_help
    
    def parseArgs(self, *rest):
        self.params.extend(rest)

    def _reportDebug(self, info):
        print 'Debug: ', info
    
    def _reportProgress(self, info):
        s = self.pb(info)
        if s:
            print '\rProgress: ', s,
        if info == 1.0:
            print '\r' + (' ' * 79) + '\r',

    def postOptions(self):
        if self.recursing:
            GeneralOptions.postOptions(self)
            return
        debug = progress = None
        if self['debug']:
            debug = self._reportDebug
        if self['progress']:
            progress = self._reportProgress
            self.pb = util.makeStatBar(60, 1.0)
        self.tapLookup = loadPlugins(debug, progress)
        self.init(self.tapLookup)
        
        self.recursing = 1
        self.parseOptions(self.params)

        if not hasattr(self, 'subOptions') or self['help']:
            print str(self)
            sys.exit(2)
        elif hasattr(self, 'subOptions'):
            if self.subOptions.has_key('help') and self.subOptions['help']:
                print str(self.subOptions)
                sys.exit(2)
        

# Rest of code in "run"

def run():
    options = FirstPassOptions()
    try:
        options.parseOptions(sys.argv[1:])
    except usage.UsageError, e:
        print str(options)
        print str(e)
        sys.exit(2)
    except (SystemExit, KeyboardInterrupt):
        sys.exit(1)
    except:
        import traceback
        print 'An error unexpected occurred:'
        print ''.join(traceback.format_exception(*sys.exc_info())[-3:])
        sys.exit(2)

    mod = getModule(options.tapLookup, options.subCommand)

    if options['uid'] is not None:
        try:
            options['uid'] = int(options['uid'])
        except ValueError:
            if not pwd:
                raise
            options['uid'] = pwd.getpwnam(options['uid'])[2]
    if options['gid'] is not None:
        try:
            options['gid'] = int(options['gid'])
        except ValueError:
            if not grp:
                raise
            options['gid'] = grp.getgrnam(options['gid'])[2]

    if not options['append']:
        a = app.Application(options.subCommand, options['uid'], options['gid'])
    else:
        if os.path.exists(options['append']):
            a = cPickle.load(open(options['append'], 'rb'))
        else:
            a = app.Application(options.subCommand, int(options['uid']), int(options['gid']))

    try:
        mod.updateApplication(a, options.subOptions)
    except usage.error, ue:
        print "Usage Error: %s" % ue
        options.subOptions.opt_help()
        sys.exit(2)
    except (SystemExit, KeyboardInterrupt):
        sys.exit(1)
    except:
        import traceback
        print 'An error unexpected occurred:'
        print ''.join(traceback.format_exception(*sys.exc_info())[-3:])
        sys.exit(2)

    if options['appname']:
        a.processName = options['appname']

    # backwards compatible interface
    if hasattr(mod, "getPorts"):
        print "The use of getPorts() is deprecated."
        for portno, factory in mod.getPorts():
            a.listenTCP(portno, factory)

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
    elif options['append']:
        a.save(filename=options['append'])
    else:
        a.save()

# Make it script-callable for testing purposes
if __name__ == "__main__":
    run()
