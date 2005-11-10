# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

import sys, os

from zope.interface import Interface, Attribute, implements
from twisted.python.components import backwardsCompatImplements

from twisted.application import service, compat, app
from twisted.persisted import sob
from twisted.python import usage, util, plugin as oldplugin
from twisted import plugin as newplugin

class IServiceMaker(Interface):
    name = Attribute(
        "A brief string naming this TAP plugin, for example \"Mega Crusher 2000\".")

    tapname = Attribute(
        "A short string naming this TAP plugin, for example \"web\" or "
        "\"pencil\".")

    description = Attribute(
        "A brief summary of the features provided by this TAP plugin.")

    options = Attribute(
        "A C{twisted.python.usage.Options} subclass defining the"
        "configuration options for this application.")

    def makeService(options):
        """Create an object implementing C{twisted.application.service.IService}

        Configure the object according to the specified options.

        @param options: A mapping (typically a C{dict} or
        C{twisted.python.usage.Options} instance) of configuration
        options to desired configuration values.
        """

try:
    import pwd, grp
except ImportError:
    def getid(uid, gid):
        if uid is not None:
            uid = int(uid)
        if gid is not None:
            gid = int(gid)
        return uid, gid
else:
    def getid(uid, gid):
        if uid is not None:
            try:
                uid = int(uid)
            except ValueError:
                uid = pwd.getpwnam(uid)[2]
        if gid is not None:
            try:
                gid = int(gid)
            except ValueError:
                gid = grp.getgrnam(gid)[2]
        return uid, gid


def loadPlugins(debug = None, progress = None):
    tapLookup = {}

    plugins = oldplugin._getPlugIns("tap", debug, progress)
    for plug in plugins:
        if hasattr(plug, 'tapname'):
            shortTapName = plug.tapname
        else:
            shortTapName = plug.module.split('.')[-1]
        tapLookup[shortTapName] = plug

    plugins = newplugin.getPlugins(IServiceMaker)
    for plug in plugins:
        tapLookup[plug.tapname] = plug

    return tapLookup

def makeService(mod, name, options):
    if hasattr(mod, 'updateApplication'):
        ser = service.MultiService()
        oldapp = compat.IOldApplication(ser)
        oldapp.name = name
        mod.updateApplication(oldapp, options)
    else:
        ser = mod.makeService(options)
    return ser

def addToApplication(ser, name, append, procname, type, encrypted, uid, gid):
    if append and os.path.exists(append):
        a = service.loadApplication(append, 'pickle', None)
    else:
        a = service.Application(name, uid, gid)
    if procname:
        service.IProcess(a).processName = procname
    ser.setServiceParent(service.IServiceCollection(a))
    sob.IPersistable(a).setStyle(type)
    passphrase = app.getSavePassphrase(encrypted)
    if passphrase:
        append = None
    sob.IPersistable(a).save(filename=append, passphrase=passphrase)

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

    optFlags = [
        ['encrypted', 'e', "Encrypt file before writing "
                           "(will make the extension of the resultant "
                           "file begin with 'e')"],
        ['debug', 'd',     "Show debug information for plugin loading"],
        ['progress', 'p',  "Show progress information for plugin loading"],
        ['help', 'h',  "Display this message"],
    ]
    #zsh_altArgDescr = {"foo":"use this description for foo instead"}
    #zsh_multiUse = ["foo", "bar"]
    #zsh_mutuallyExclusive = [("foo", "bar"), ("bar", "baz")]
    zsh_actions = {"append":'_files -g "*.tap"',
                   "type":"(pickle xml source)"}
    zsh_actionDescr = {"append":"tap file to append to", "uid":"uid to run as",
                       "gid":"gid to run as", "type":"output format"}

    def init(self, tapLookup):
        sc = []
        for (name, module) in tapLookup.iteritems():
            if IServiceMaker.providedBy(module):
                sc.append((
                    name, None, lambda m=module: m.options(), module.description))
            else:
                sc.append((
                    name, None, lambda obj=module: obj.load().Options(),
                    getattr(module, 'description', '')))

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
        try:
            self.tapLookup = loadPlugins(debug, progress)
        except IOError:
            raise usage.UsageError("Couldn't load the plugins file!")
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
        print e
        sys.exit(2)
    except KeyboardInterrupt:
        sys.exit(1)

    plg = options.tapLookup[options.subCommand]
    if not IServiceMaker.providedBy(plg):
        plg = plg.load()
    ser = makeService(plg, options.subCommand, options.subOptions)
    addToApplication(ser,
                     options.subCommand, options['append'], options['appname'],
                     options['type'], options['encrypted'],
                     *getid(options['uid'], options['gid']))

from twisted.python.reflect import namedAny
from twisted.plugin import IPlugin

class _tapHelper(object):
    """
    Internal utility class to simplify the definition of \"new-style\"
    mktap plugins based on existing, \"classic\" mktap plugins.
    """

    implements(IPlugin, IServiceMaker)

    def __init__(self, name, module, description, tapname):
        self.name = name
        self.module = module
        self.description = description
        self.tapname = tapname

    def options():
        def get(self):
            return namedAny(self.module).Options
        return get,
    options = property(*options())

    def makeService():
        def get(self):
            return namedAny(self.module).makeService
        return get,
    makeService = property(*makeService())
backwardsCompatImplements(_tapHelper)
