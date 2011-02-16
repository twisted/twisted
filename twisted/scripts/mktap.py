# -*- test-case-name: twisted.scripts.test.test_mktap -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import warnings, sys, os


from twisted.application import service, app
from twisted.persisted import sob
from twisted.python import usage, util
from twisted import plugin
from twisted.python.util import uidFromString, gidFromString

# API COMPATIBILITY
IServiceMaker = service.IServiceMaker
_tapHelper = service.ServiceMaker

warnings.warn(
    "mktap and related support modules are deprecated as of Twisted 8.0.  "
    "Use Twisted Application Plugins with the 'twistd' command directly, "
    "as described in 'Writing a Twisted Application Plugin for twistd' "
    "chapter of the Developer Guide.", DeprecationWarning, stacklevel=2)



def getid(uid, gid):
    """
    Convert one or both of a string representation of a UID and GID into
    integer form.  On platforms where L{pwd} and L{grp} is available, user and
    group names can be converted.

    @type uid: C{str} or C{NoneType}
    @param uid: A string giving the base-ten representation of a UID or the
        name of a user which can be converted to a UID via L{pwd.getpwnam},
        or None if no UID value is to be obtained.

    @type gid: C{str} or C{NoneType}
    @param uid: A string giving the base-ten representation of a GID or the
        name of a group which can be converted to a GID via
        L{grp.getgrnam}, or None if no UID value is to be obtained.

    @return: A two-tuple giving integer UID and GID information for
        whichever (or both) parameter is provided with a non-C{None} value.

    @raise ValueError: If a user or group name is supplied and L{pwd} or L{grp}
        is not available.
    """
    if uid is not None:
        uid = uidFromString(uid)
    if gid is not None:
        gid = gidFromString(gid)
    return (uid, gid)



def loadPlugins(debug = None, progress = None):
    tapLookup = {}

    plugins = plugin.getPlugins(IServiceMaker)
    for plug in plugins:
        tapLookup[plug.tapname] = plug

    return tapLookup

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
        ['uid', 'u', None, "The uid to run as.", uidFromString],
        ['gid', 'g', None, "The gid to run as.", gidFromString],
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
    ser = plg.makeService(options.subOptions)
    addToApplication(ser,
                     options.subCommand, options['append'], options['appname'],
                     options['type'], options['encrypted'],
                     options['uid'], options['gid'])
