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
        return "<Coil Plugin %s %s%s>" % (repr(self.name), self.module, loaded)

class DropIn:
    """I am a Python package contianing plugins.tml.
    """
    def __init__(self, name):
        self.name = name
        self.plugins = []

    def register(self, name, module, **kw):
        """Register a new plug-in.
        """
        self.plugins.append(apply(PlugIn, (name, module), kw))

    def __repr__(self):
        return "<Coil Package %s %s>" % (self.name, self.plugins)

def getPlugIns(plugInType, debugInspection=0, showProgress=0):
    loaded = {}
    result = []
    if showProgress:
        log.logfile.write(' Loading: [')
        log.logfile.flush()
    found = 0
    for d in sys.path:
        d = os.path.abspath(d)
        if loaded.has_key(d):
            if debugInspection:
                log.msg('already saw %s' % d)
            continue
        else:
            if debugInspection:
                log.msg('looking at %s' % d)
            loaded[d] = 1
        if os.path.isdir(d):
            for plugindir in os.listdir(d):
                plugindir = os.path.join(d, plugindir)
                if os.path.isdir(plugindir):
                    if showProgress:
                        log.logfile.write('-')
                        log.logfile.flush()
                    tmlname = os.path.join(plugindir, "plugins.tml")
                    pname = os.path.split(os.path.abspath(plugindir))[-1]
                    if debugInspection:
                        log.msg(tmlname)
                    if os.path.exists(tmlname):
                        dropin = DropIn(pname)
                        ns = {'register': dropin.register}
                        try:
                            execfile(tmlname, ns)
                        except:
                            if debugInspection:
                                import traceback
                                print "Exception in %s:"
                                traceback.print_exc()
                            else:
                                print "Exception in %s (use --debug for more info)" % (tmlname,)
                            continue
                        found = 1
                        if showProgress:
                            log.logfile.write('+')
                            log.logfile.flush()
                        for plugin in dropin.plugins:
                            if plugInType == plugin.type:
                                result.append(plugin)
                        if debugInspection:
                            log.msg("Successfully loaded %s!" % plugindir)

        else:
            if debugInspection:
                log.msg('sys.path entry not a directory %s' % d)
        if showProgress:
            log.logfile.write('.')
            log.logfile.flush()
    if not found:
        raise IOError("Couldn't find a plugins file!")
    if showProgress:
        log.logfile.write(' ]\n')
        log.logfile.flush()
    return result
