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
import errno

# Twisted imports
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
        """Check to see if the module for this plugin has been imported yet.
        
        @rtype: C{int}
        @return: A true value if the module for this plugin has been loaded,
        false otherwise.
        """
        return sys.modules.has_key(self.module)

    def load(self):
        """Load the module for this plugin.
        
        @rtype: C{ModuleType}
        @return: The module object that is loaded.
        """
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
        self.plugins.append(PlugIn(name, module, **kw))

    def __repr__(self):
        return "<Package %s %s>" % (self.name, self.plugins)


def getPluginFileList(debugInspection=0, showProgress=0):
    """Find plugin.tml files in C{sys.path}

    @type debugInspection: C{int}
    @param debugInspection: If true, debug information about the loading
    process is printed.
    
    @type showProgress: C{int}
    @param showProgress: If true, an indication of the loading progress is
    printed.
    
    @rtype: C{list} of C{str}
    @return: A list of the plugin.tml files found.
    """
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

        try:
            paths = os.listdir(d)
        except OSError, (err, s):
            # Permission denied, carry on
            if err == errno.EACCES:
                if showProgress:
                    log.logfile.write('x')
                    log.logfile.flush()
                if debugInspection:
                    log.msg('Permission denied on ' + d)
            else:
                raise
        else:
            for plugindir in paths:
                if seenNames.has_key(plugindir):
                    continue
                seenNames[plugindir] = 1
                plugindir = os.sep.join((d, plugindir))
                if showProgress:
                    log.logfile.write('+')
                    log.logfile.flush()
                tmlname = os.sep.join((plugindir, "plugins.tml"))
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
    """Traverse the given list of files and attempt to load plugins from them.

    @type plugInType: C{str}
    @param plugInType: The type of plugin to search for.  This is tested
    against the C{type} argument to the C{register} function in the
    plugin.tml files.
    
    @type fileList: C{list} of C{str}
    @param fileList: A list of the files to attempt to load plugin
    information from.  One name is put in their scope, the C{register}
    function.
    
    @type debugInspection: C{int}
    @param debugInspection: If true, debug information about the loading
    process is printed.
    
    @type showProgress: C{int}
    @param showProgress: If true, an indication of the loading progress is
    printed.

    @rtype C{list}
    @return: A list of the C{PlugIn} objects found.
    """
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
    """Helper function to get all the plugins of a particular type.
    
    @type plugInType: C{str}
    @param plugInType: The type of plugin to search for.  This is tested
    against the C{type} argument to the C{register} function in the
    plugin.tml files.
    
    @type debugInspection: C{int}
    @param debugInspection: If true, debug information about the loading
    process is printed.
    
    @type showProgress: C{int}
    @param showProgress: If true, an indication of the loading progress is
    printed.
    
    @rtype: C{list}
    @return: A list of C{PlugIn} objects that were found.
    """
    tmlFiles = getPluginFileList(debugInspection, showProgress)
    return loadPlugins(plugInType, tmlFiles, debugInspection, showProgress)
