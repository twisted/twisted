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
    dirs = sys.path
    import twisted
    result = []
    plugindirs = []
    if showProgress:
        sys.stdout.write(' Loading: [')
        sys.stdout.flush()
    for d in dirs:
        d = os.path.abspath(d)
        if loaded.has_key(d):
            continue
        else:
            loaded[d] = 1
        if os.path.isdir(d):
            for plugindir in os.listdir(d):
                if os.path.isdir(plugindir):
                    plugindir = os.path.join(d, plugindir)
                    if showProgress:
                        sys.stdout.write('-')
                        sys.stdout.flush()
                    tmlname = os.path.join(plugindir, "plugins.tml")
                    pname = os.path.split(os.path.abspath(plugindir))[-1]
                    if os.path.exists(tmlname):
                        dropin = DropIn(pname)
                        ns = {'register': dropin.register}
                        execfile(tmlname, ns)
                        if showProgress:
                            sys.stdout.write('+')
                            sys.stdout.flush()
                        for plugin in dropin.plugins:
                            if plugInType == plugin.type:
                                result.append(plugin)
                        if debugInspection:
                            print "Successfully loaded %s!" % plugindir
        if showProgress:
            sys.stdout.write('.')
            sys.stdout.flush()
    if showProgress:
        sys.stdout.write(' ]\n')
        sys.stdout.flush()
    return result
