
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
from twisted.application import service, compat, app
from twisted.python import usage, util, plugin
import sys, os
try:
    import pwd, grp
except ImportError:
    def getid(uid, gid):
        return map(int, (uid or 0, gid or 0))
else:
    def getid(uid, gid):
        try:
            uid = int(uid or 0)
        except ValueError:
            uid = pwd.getpwnam(uid)[2]
        try:
            gid = int(gid or 0)
        except ValueError:
            gid = grp.getgrnam(gid)[2]
        return uid, gid


def loadPlugins(debug = None, progress = None):
    try:
        plugins = plugin.getPlugIns("tap", debug, progress)
    except IOError:
        raise usage.UsageError("Couldn't load the plugins file!")
    tapLookup = {}
    for plug in plugins:
        if hasattr(plug, 'tapname'):
            shortTapName = plug.tapname
        else:
            shortTapName = plug.module.split('.')[-1]
        tapLookup[shortTapName] = plug
    return tapLookup

def makeService(mod, s, options):
    if hasattr(mod, 'updateApplication'):
        ser = service.MultiService()
        mod.updateApplication(compat.IOldApplication(ser), options)
    else:
        ser = mod.makeService(options)
    ser.setServiceParent(s)

def makeApplication(module, name, append, procname, type, encrypted, options,
                    uid, gid):
    a = app.loadOrCreate(name, append, procname, uid, gid)
    makeService(module, service.IServiceCollection(a), options)
    app.saveApplication(a, type, encrypted, append)

class FirstPassOptions(usage.Options):
    synopsis = """Usage:    mktap [options] <command> [command options] """

    recursing = 0
    params = ()
    
    optParameters = [
        ['uid', 'u', None, "The uid to run as."],
        ['gid', 'g', None, "The gid to run as."],
        ['append', 'a', None,
         "An existing .tap file to append the plugin to, rather than "
         "creating a new one."],
        ['type', 't', 'pickle',
         "The output format to use; this can be 'pickle', 'xml', "
         "or 'source'."],
        ['appname', 'n', None, "The process name to use for this application."]
    ]
    if hasattr(os, 'getgid'):
        optParameters[0][2], optParameters[1][2] = os.getuid(), os.getgid()

    optFlags = [
        ['encrypted', 'e', "Encrypt file before writing "
                           "(will make the extension of the resultant "
                           "file begin with 'e')"],
        ['debug', 'd',     "Show debug information for plugin loading"],
        ['progress', 'p',  "Show progress information for plugin loading"],
        ['help', 'h',  "Display this message"],
    ]

    def init(self, tapLookup):
        sc = [ [name, None, (lambda obj=module:obj.load().Options()),
                getattr(module, 'description', '')]
                                     for name, module in tapLookup.items()]
        sc.sort()
        self.subCommands = sc

    def parseArgs(self, *rest):
        self.params += rest

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
            raise usage.UsageError(str(self))
        if hasattr(self, 'subOptions') and self.subOptions.get('help'):
            raise usage.UsageError(str(self.subOptions))
        if not self.tapLookup.has_key(self.subCommand):
            raise usage.UsageError("Please select one of: "+
                                   ' '.join(self.tapLookup))
       

def run():
    options = FirstPassOptions()
    try:
        options.parseOptions(sys.argv[1:])
    except usage.UsageError, e:
        print "%s\n%s" % (options, e)
        sys.exit(2)
    except KeyboardInterrupt:
        sys.exit(1)
    makeApplication(options.tapLookup[options.subCommand].load(),
                    options.subCommand, options['append'], options['appname'],
                    options['type'],
                    options['encrypted'], options.subOptions,
                    *getid(options['uid'], options['gid']))
