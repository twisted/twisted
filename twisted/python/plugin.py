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
import types
import warnings

# Twisted imports
from twisted.python import log, util

# Sibling Imports
from reflect import namedModule

try:
    from os.path import realpath as cacheTransform
except ImportError:
    from os.path import abspath as cacheTransform

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


def _prepCallbacks(debug, progress):
    if debug:
        try:
            debug('Looking for plugin.tml files')
        except:
            debug = lambda x: sys.stdout.write(x + '\n')
            debug('Looking for plugin.tml files')
    else:
        debug = lambda x: None
    if progress:
        try:
            progress(0.0)
        except:
            pb = util.makeStatusBar(76)
            progress = lambda x, pb=pb: sys.stdout.write(pb(x) + '\r')
            progress(0.0)
    else:
        progress = lambda x: None
    return debug, progress

def getPluginFileList(debugInspection=None, showProgress=None):
    """Find plugin.tml files in subdirectories of paths in C{sys.path}

    @type debugInspection: C{None} or a callable taking one argument
    @param debugInspection: If not None, this is invoked with strings containing
    debug information about the loading process.  If it is any other true value,
    this debug information is written to stdout (This behavior is deprecated).
    
    @type showProgress: C{None} or a callable taking one argument.
    @param showProgress: If not None, this is invoked with floating point
    values between 0 and 1 describing the progress of the loading process. 
    If it is any other true value, this progress information is written to
    stdout.  (This behavior is deprecated).

    @rtype: C{list} of C{str}
    @return: A list of the plugin.tml files found.
    """
    if isinstance(debugInspection, types.IntType):
        warnings.warn(
            "int parameter for debugInspection is deprecated, pass None or "
            "a function that takes a single argument instead.",
            DeprecationWarning, 2
        )
    if isinstance(showProgress, types.IntType):
        warnings.warn(
            "int parameter for showProgress is deprecated, pass None or "
            "a function that takes a single argument instead.",
            DeprecationWarning, 2
        )
    debugInspection, showProgress = _prepCallbacks(debugInspection, showProgress)
    exists = os.path.exists
    join = os.sep.join
    result = []
    loaded = {}
    seenNames = {}
    paths = filter(os.path.isdir, map(cacheTransform, sys.path))
    # special case for commonly used directories we *know* shouldn't be checked
    # and really slow down mktap and such-like in real installations
    for p in ("/usr/bin", "/usr/local/bin"):
        try:
            paths.remove(p)
        except ValueError:
            pass
    progress = 0.0
    increments = 1.0 / len(paths)

    for (index, d) in zip(range(len(paths)), paths):
        showProgress(progress)
        if loaded.has_key(d):
            debugInspection('Already saw ' + d)
            continue
        else:
            debugInspection('Recursing through ' + d)
        try:
            subDirs = os.listdir(d)
        except OSError, (err, s):
            # Permission denied, carry on
            if err == errno.EACCES:
                debugInspection('Permission denied on ' + d)
            else:
                raise
        else:
            # filter out files we obviously don't need to check - ones with '.' in them
            subDirs = [s for s in subDirs if "." not in s]
            if not subDirs:
                continue
            incr = increments * (1.0 / len(subDirs))
            for plugindir in subDirs:
                if seenNames.has_key(plugindir):
                    debugInspection('Seen %s already' % plugindir)
                    continue
                tmlname = join((d, plugindir, "plugins.tml"))
                if isAModule(join((d,plugindir))):
                    seenNames[plugindir] = 1
                    if exists(tmlname):
                        result.append(tmlname)
                        debugInspection('Found ' + tmlname)
                    else:
                        debugInspection('Failed ' + tmlname)
                else:
                    debugInspection('Not a module ' + tmlname)
                progress = progress + incr
                showProgress(progress)

    if not result:
        raise IOError("Couldn't find a plugins file!")
    showProgress(1.0)
    return result

def loadPlugins(plugInType, fileList, debugInspection=None, showProgress=None):
    """Traverse the given list of files and attempt to load plugins from them.

    @type plugInType: C{str}
    @param plugInType: The type of plugin to search for.  This is tested
    against the C{type} argument to the C{register} function in the
    plugin.tml files.
    
    @type fileList: C{list} of C{str}
    @param fileList: A list of the files to attempt to load plugin
    information from.  One name is put in their scope, the C{register}
    function.
    
    @type debugInspection: C{None} or a callable taking one argument
    @param debugInspection: If not None, this is invoked with strings containing
    debug information about the loading process.  If it is any other true value,
    this debug information is written to stdout (This behavior is deprecated).
    
    @type showProgress: C{None} or a callable taking one argument.
    @param showProgress: If not None, this is invoked with floating point
    values between 0 and 1 describing the progress of the loading process. 
    If it is any other true value, this progress information is written to
    stdout.  (This behavior is deprecated).

    @rtype: C{list}
    @return: A list of the C{PlugIn} objects found.
    """
    if isinstance(debugInspection, types.IntType):
        warnings.warn(
            "int parameter for debugInspection is deprecated, pass None or "
            "a function that takes a single argument instead.",
            DeprecationWarning, 2
        )
    if isinstance(showProgress, types.IntType):
        warnings.warn(
            "int parameter for showProgress is deprecated, pass None or "
            "a function that takes a single argument instead.",
            DeprecationWarning, 2
        )
    result = []
    debugInspection, showProgress = _prepCallbacks(debugInspection, showProgress)
    
    increments = 1.0 / len(fileList)
    progress = 0.0

    for (index, tmlFile) in zip(range(len(fileList)), fileList):
        showProgress(progress)
        debugInspection("Loading from " + tmlFile)
        pname = os.path.split(os.path.abspath(tmlFile))[-2]
        dropin = DropIn(pname)
        ns = {'register': dropin.register}
        try:
            execfile(tmlFile, ns)
        except (IOError, OSError), e:
            # guess we don't have permissions for that
            debugInspection("Error loading: %s" % e)
            continue
        
        ldp = len(dropin.plugins) or 1.0
        incr = increments * (1.0 / ldp)
        for plugin in dropin.plugins:
            if plugInType == plugin.type:
                result.append(plugin)
                debugInspection("Found %r" % (plugin,))
            else:
                debugInspection("Disqualified %r" % (plugin,))
            progress = progress + incr
            showProgress(progress)
        debugInspection("Finished loading from %s!" % tmlFile)

    showProgress(1.0)
    debugInspection("Returning %r" % (result,))
    return result

def getPlugIns(plugInType, debugInspection=None, showProgress=None):
    """Helper function to get all the plugins of a particular type.
    
    @type plugInType: C{str}
    @param plugInType: The type of plugin to search for.  This is tested
    against the C{type} argument to the C{register} function in the
    plugin.tml files.
    
    @type debugInspection: C{None} or a callable taking one argument
    @param debugInspection: If not None, this is invoked with strings containing
    debug information about the loading process.  If it is any other true value,
    this debug information is written to stdout (This behavior is deprecated).
    
    @type showProgress: C{None} or a callable taking one argument.
    @param showProgress: If not None, this is invoked with floating point
    values between 0 and 1 describing the progress of the loading process. 
    If it is any other true value, this progress information is written to
    stdout.  (This behavior is deprecated).

    @rtype: C{list}
    @return: A list of C{PlugIn} objects that were found.
    """
    if isinstance(debugInspection, types.IntType):
        warnings.warn(
            "int parameter for debugInspection is deprecated, pass None or "
            "a function that takes a single argument instead.",
            DeprecationWarning, 2
        )
    if isinstance(showProgress, types.IntType):
        warnings.warn(
            "int parameter for showProgress is deprecated, pass None or "
            "a function that takes a single argument instead.",
            DeprecationWarning, 2
        )
    debugInspection, showProgress = _prepCallbacks(debugInspection, showProgress)

    firstHalf = secondHalf = lambda x: None
    if showProgress:
        firstHalf = lambda x: showProgress(x / 2.0)
        secondHalf = lambda x: showProgress(x / 2.0 + 0.5)

    tmlFiles = getPluginFileList(debugInspection, firstHalf)
    return loadPlugins(plugInType, tmlFiles, debugInspection, secondHalf)

def isAModule(d):
    """This function checks the directory for __init__ files.
    """
    suffixes = ['py', 'pyc', 'pyo', 'so', 'pyd', 'dll']
    exists = os.path.exists
    join = os.sep.join
    for s in suffixes: # bad algorithm, but probably works
        if exists(join((d,'__init__.%s' % s))):
            return 1
    return 0

__all__ = ['PlugIn', 'DropIn', 'getPluginFileList', 'loadPlugins', 'getPlugIns']
