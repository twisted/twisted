
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
from twisted.application import service, compat
from twisted.persisted import sob
from twisted.python import usage, util, plugin
import sys, traceback, os
try:
    import cPickle
except ImportError:
    import pickle as cPickle
try:
    import pwd
except ImportError:
    pwd = None
try:
    import grp
except ImportError:
    grp = None

def getid(uid, gid):
    if uid is not None:
        try:
            uid = int(uid)
        except ValueError:
            if not pwd:
                raise
            uid = pwd.getpwnam(uid)[2]
    if gid is not None:
        try:
            gid = int(gid)
        except ValueError:
            if not grp:
                raise
            gid = grp.getgrnam(gid)[2]
    return uid, gid

def saveApplications(p, type, enc, filename):
    p.setStyle(type)
    p.save(filename=(not enc) and filename,
           passphrase=enc and util.getPassword("Encryption passphrase: "))


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
        ['append', 'a', None,
         "An existing .tap file to append the plugin to, rather than "
         "creating a new one."],
        ['type', 't', 'pickle',
         "The output format to use; this can be 'pickle', 'xml', "
         "or 'source'."],
        ['appname', 'n', None, "The process name to use for this application."]
    ]
    del uid, gid

    optFlags = [
        ['encrypted', 'e', "Encrypt file before writing "
                           "(will make the extension of the resultant "
                           "file begin with 'e')"],
        ['debug', 'd',     "Show debug information for plugin loading"],
        ['progress', 'p',  "Show progress information for plugin loading"],
    ]

    def init(self, tapLookup):
        self.subCommands = []
        for (x, y) in tapLookup.items():
            self.subCommands.append(
                [x,
                 None,
                 (lambda obj = y: obj.load().Options()),
                 getattr(y, 'description', '')]
             )
        self.subCommands.sort()
        self['help'] = 0 # default

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
        

def getApplication(uid, gid, filename):
    if filename and os.path.exists(filename):
        return sob.load(filename, 'pickle')
    else:
        uid, gid = getid(uid, gid):
        return service.Application(options.subCommand, uid, gid)

def makeService(mod, s):
    if hasattr(mod, 'updateApplication'):
        mod.updateApplication(compat.IOldApplication(s), options.subOptions)
    else:
        mod.makeService(options.subOptions).setServiceParent(s)

def run():
    options = FirstPassOptions()
    try:
        options.parseOptions(sys.argv[1:])
    except usage.UsageError, e:
        print "%s\n%s" % (options, e)
        sys.exit(2)
    except KeyboardInterrupt:
        sys.exit(1)
    mod = getModule(options.tapLookup, options.subCommand)
    a = getApplication(options['uid'], options['gid'], options['append'])
    if options['appname']:
        service.IProcess(a).processName = options['appname']
    s = service.IServiceCollection(a)
    try:
        makeService(mod, s)
    except usage.error, ue:
        print "Usage Error: %s" % ue
        options.subOptions.opt_help()
        sys.exit(2)
    except KeyboardInterrupt:
        sys.exit(1)
    saveApplication(sob.IPersistant(a),
                    options['type'], options['encrypted'], options['append'])
