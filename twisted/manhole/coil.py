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


## THIS CODE IS NOT FINISHED YET. ##

# System Imports
import types
import string
import sys
import new
import os

# Twisted Imports
from twisted.python import util

"""Twisted COIL: COnfiguration ILlumination.

An end-user direct-manipulation interface to Twisted, accessible through the
web.
"""

def getAllBases(inClass):
    """Get all super-classes of a given class.

    Recursively determine the entire hierarchy above a certain class, and
    return it as a list.
    """
    classes = list(inClass.__bases__)
    for base in inClass.__bases__:
        classes.extend(getAllBases(base))
    return util.uniquify(classes)

def getClass(name):
    """Turn a fully-qualified class name into a class.

    This assumes that the class has already been imported and will raise an
    undefined exception if it has not.
    """
    name = string.split(name, '.')
    obj = sys.modules[name[0]]
    for n in name[1:]:
        obj = getattr(obj, n)
    return obj

class ClassHierarchy:
    """A class which represents a hierarchy of classes.

    It's possible in python to identify all base classes of a particular class
    fairly easily, but not to identify all of its subclasses.  This class
    allows you to register and then query for sub-classes of a given class.
    """
    def __init__(self):
        self.classes = {}

    def getSubClasses(self, classOrString, asClasses=0):
        """Get a tuple of all registered subclasses of a given class.

        The class may be specified either by the actual class or a descriptive
        string.  An optional flag, asClasses, specifies whether those classes
        should be returned as class objects or as strings.  By default, I will
        return strings.
        """
        if isinstance(classOrString, types.ClassType):
            className = str(classOrString)
        else:
            className = classOrString
        if not self.classes.has_key(className):
            print 'no class %s registered' % className
            return []
        superClasses, subClasses = self.classes[className]
        if asClasses:
            return tuple(map(getClass, subClasses))
        else:
            return tuple(subClasses)

    def getSuperClasses(self, classOrString, asClasses=0):
        """Get a tuple of all registered superclasses of a given class.

        The class may be specified either by the actual class or a descriptive
        string.  An optional flag, asClasses, specifies whether those classes
        should be returned as class objects or as strings.  By default, I will
        return strings.
        """
        if isinstance(classOrString, types.ClassType):
            className = str(classOrString)
        else:
            className = classOrString
        superClasses, subClasses = self.classes[className]
        if asClasses:
            return tuple(map(getClass, superClasses))
        else:
            return tuple(superClasses)

    def registerClass(self, inClass):
        """Register a class.
        """
        className = str(inClass)
        if self.classes.has_key(className):
            superClasses, subClasses = self.classes[className]
        else:
            superClasses, subClasses = [], []
            self.classes[className] = superClasses, subClasses
        for base in getAllBases(inClass):
            baseName = str(base)
            if baseName not in superClasses:
                self.registerClass(base)
                baseSuper, baseSub = self.classes[str(base)]
                baseSub.append(className)
                superClasses.append(baseName)

theClassHierarchy = ClassHierarchy()
registerClass = theClassHierarchy.registerClass


class InvalidConfiguration(Exception):
    """I am is raised in the case of an invalid configuration.
    """

def createConfigurable(configClass, container, name):
    """Instantiate a configurable.

    First, I will create an instance object of class configClass.
    Then I will call its configInit, with 'container' and 'name'
    as arguments.  If the class passed in is not a subclass of
    Configurable, I will fail.
    """
    if not issubclass(configClass, Configurable):
        raise TypeError("%s is not a subclass of %s" %
                        (configClass, Configurable))
    instance = new.instance(configClass, {})
    instance.configInit(container, name)
    return instance

class Configurable:
    """A configurable object.

    I have a dictionary attribute, configTypes, that indicates what sort of
    objects I will allow to be configured.  It is a mapping of variable names
    to variable types.  Variable types may be either python type objects,
    classes, or objects describing a desired 'hint' to the interface (such as
    'boolean' or ['choice', 'a', 'b', 'c']). (XXX Still in flux.)

    I have a list attribute, configDispensers, that indicates what methods on
    me may be called with no arguments to create an instance of another
    Configurable.  It is a list of the form [(method name, class, descString), ...].

    Custom handling of configuration-item-setting can be had by adding
    configure_%s(self, value) methods to my subclass.
    """

    # Change this attribute in subclasses.
    configTypes = {}

    configName = None

    configDispensers = []

    configCreatable = 1

    def __init__(self):
        """Initialize me.

        Note that I need to be initialized even if you're initializing directly
        from configInit; if you subclass me, be sure to run
        Configurable.__init__(self) inside configInit if you override it.
        """
        self.configuration = {}

    def configInit(self, container, name):
        """Initialize me to a base state from which it may be configured.

        By default, I will run self.__init__ with no arguments.
        """
        self.__init__()

    def configure(self, dict):
        """Set a list of configuration variables.
        """
        items = dict.items()
        getType = self.configTypes.get
        for name, value in items:
            t = getType(name, None)
            if isinstance(t, types.TypeType) or isinstance(t, types.ClassType):
                if not isinstance(value, t) or (value is None):
                    raise InvalidConfiguration("type mismatch")
            elif t == 'boolean':
                try:
                    if value: pass
                except:
                    raise InvalidConfiguration("non-boolean for boolean type")
            else:
                raise InvalidConfiguration("Configuration item '%s' has "
                                           "unknown type '%s'" % (name, t))

        for name, value in items:
            func = getattr(self, "config_%s" % name, None)
            if func:
                func(value)
            else:
                self.configuration[name] = value

    def getConfiguration(self):
        """Return a mapping of key/value tuples describing my configuration.
        """
        return self.configuration

class Module:
    def __init__(self, name, module, description):
        self.name = name
        self.module = module
        self.description = description

    def isImported(self):
        return sys.modules.has_key(self.module)

    def doImport(self):
        __import__(self.module)

    def __repr__(self):
        return "<Coil Module %s %s %s>" % (self.name, self.module, self.isImported())

class Package:
    def __init__(self, name):
        self.name = name
        self.modules = []

    def register(self, name, module, description):
        self.modules.append(Module(name, module, description))

    def __repr__(self):
        return "<Coil Package %s %s>" % (self.name, self.modules)

def getModuleList():
    dirs = util.getPluginDirs()
    import twisted
    result = []
    plugindirs = []
    for d in dirs:
        if os.path.exists(d):
            for plugindir in os.listdir(d):
                plugindirs.append(os.path.join(d, plugindir))
    plugindirs.append(
        apply(os.path.join,
              os.path.split(os.path.dirname(twisted.__file__))))
    for plugindir in plugindirs:
        tmlname = os.path.join(plugindir, "modules.tml")
        pname = os.path.split(os.path.abspath(plugindir))[-1]
        if os.path.exists(tmlname):
            p = Package(pname)
            ns = {'register': p.register}
            execfile(tmlname, ns)
            result.append(p)
            print "Successfully loaded %s!" % plugindir
        elif os.path.exists(os.path.join(plugindir,'__init__.py')):
            print "module %s has no modules index. (%s)" % (pname, plugindir)
    return result
