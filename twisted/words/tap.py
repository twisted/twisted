# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Shiny new words service maker
"""

import sys, socket

from twisted.application import strports
from twisted.application.service import MultiService
from twisted.python import usage
from twisted import plugin

from twisted.words import iwords, service
from twisted.cred import checkers, portal

class Options(usage.Options):
    optParameters = [
        ('passwd', None, None,
         'Name of a passwd-style password file. (REQUIRED)'),
        ('hostname', None, socket.gethostname(),
         'Name of this server; purely an informative')]

    interfacePlugins = {}
    plg = None
    for plg in plugin.getPlugins(iwords.IProtocolPlugin):
        assert plg.name not in interfacePlugins
        interfacePlugins[plg.name] = plg
        optParameters.append((
            plg.name + '-port',
            None, None,
            'strports description of the port to bind for the  ' + plg.name + ' server'))
    del plg

    def __init__(self, *a, **kw):
        usage.Options.__init__(self, *a, **kw)
        self['groups'] = []


    def opt_group(self, name):
        """Specify a group which should exist
        """
        self['groups'].append(name.decode(sys.stdin.encoding))


    def postOptions(self):
        if not self['passwd']:
            raise usage.UsageError("You must supply a password file")


def makeService(config):
    if config['passwd']:
        checker = checkers.FilePasswordDB(config['passwd'], cache=True)

    wordsRealm = service.InMemoryWordsRealm(config['hostname'])
    wordsPortal = portal.Portal(wordsRealm, [checker])

    msvc = MultiService()

    # XXX Attribute lookup on config is kind of bad - hrm.
    for plgName in config.interfacePlugins:
        port = config.get(plgName + '-port')
        if port is not None:
            factory = config.interfacePlugins[plgName].getFactory(wordsRealm, wordsPortal)
            svc = strports.service(port, factory)
            svc.setServiceParent(msvc)

    # This is bogus.  createGroup is async.  makeService must be
    # allowed to return a Deferred or some crap.
    for g in config['groups']:
        wordsRealm.createGroup(g)

    return msvc
