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

from __future__ import nested_scopes

# System Imports
import sys
import os

from twisted.python import log

# Sibling Imports
from reflect import namedModule


class PlugIn:
    """I am a Python module registered in a plugins.tml file.
    """
    def __init__(self, name, module, **kw):
        self.name = name
        self.module = module
        for key, value in kw.items():
            setattr(self, key, value)

    def isLoaded(self):
        return sys.modules.has_key(self.module)

    def load(self):
        return namedModule(self.module)

    def __repr__(self):
        if self.isLoaded():
            loaded = ' loaded'
        else:
            loaded = ''
        return "<Plugin %s %s%s>" % (repr(self.name), self.module, loaded)

class DropIn:
    """I am a Python package containing plugins.tml.
    """
    def __init__(self, name):
        self.name = name
        self.plugins = []

    def register(self, name, module, **kw):
        """Register a new plug-in.
        """
        self.plugins.append(apply(PlugIn, (name, module), kw))

    def __repr__(self):
        return "<Package %s %s>" % (self.name, self.plugins)


def getPluginFileList(debugInspection=0, showProgress=0):
    result = []
    loaded = {}
    if showProgress:
        log.logfile.write(' Looking for plugins.tml files: [')
        log.logfile.flush()
    found = 0

    seenNames = {}
    for d in filter(os.path.isdir, map(os.path.abspath, sys.path)):
        if loaded.has_key(d):
            if debugInspection:
                log.msg('already saw %s' % d)
            continue
        else:
            if debugInspection:
                log.msg('Recursing through %s' % d)
            loaded[d] = 1

        for plugindir in os.listdir(d):
            if seenNames.has_key(plugindir):
                continue
            seenNames[plugindir] = 1
            plugindir = os.path.join(d, plugindir)
            if showProgress:
                log.logfile.write('+')
                log.logfile.flush()
            tmlname = os.path.join(plugindir, "plugins.tml")
            if debugInspection:
                log.msg(tmlname)
            if os.path.exists(tmlname):
                found = 1
                result.append(tmlname)

    if not found:
        raise IOError("Couldn't find a plugins file!")

    if showProgress:
        log.logfile.write(']\n')
        log.logfile.flush()

    return result

def loadPlugins(plugInType, fileList, debugInspection=0, showProgress=0):
    result = []
    if showProgress:
        log.logfile.write('Loading plugins.tml files: [')
        log.logfile.flush()

    for tmlFile in fileList:
        try:
            pname = os.path.split(os.path.abspath(tmlFile))[-2]
            dropin = DropIn(pname)
            ns = {'register': dropin.register}
            execfile(tmlFile, ns)
        except:
            if debugInspection:
                import traceback
                print "Exception in %s:" % (tmlFile,)
                traceback.print_exc()
            else:
                print "Exception in %s (use --debug for more info)" % tmlFile
            continue

        if showProgress:
            log.logfile.write('+')
            log.logfile.flush()
        for plugin in dropin.plugins:
            if plugInType == plugin.type:
                result.append(plugin)

        if debugInspection:
            log.msg("Successfully loaded %s!" % tmlFile)

        if showProgress:
            log.logfile.write('.')
            log.logfile.flush()

    if showProgress:
        log.logfile.write(']\n')
        log.logfile.flush()

    return result

def getPlugIns(plugInType, debugInspection=0, showProgress=0):
    tmlFiles = getPluginFileList(debugInspection, showProgress)
    return loadPlugins(plugInType, tmlFiles, debugInspection, showProgress)
