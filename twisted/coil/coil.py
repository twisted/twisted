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

"""Twisted COIL: COnfiguration ILlumination.

An end-user direct-manipulation interface to Twisted, accessible through the
web.

This is a work in progress.
"""

# System Imports
import types
import string
import sys
import os

# Twisted Imports
from twisted.python.util import uniquify, getPluginDirs
from twisted.python import log


def getAllBases(inClass):
    """Get all super-classes of a given class.

    Recursively determine the entire hierarchy above a certain class, and
    return it as a list.
    """
    # in older versions of jython list() doesn't return a copy
    classes = list(inClass.__bases__)[:]
    for base in inClass.__bases__:
        classes.extend(getAllBases(base))
    return uniquify(classes)


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
            log.msg('no class %s registered' % className)
            return ()
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
configurators = {}
configurables = {}
factories = {}

def registerConfigurator(configuratorClass, factory):
    """Register a configurator and factory for a class.
    
    If factory is None then new instances will not be created directly
    by coil.
    """
    configurableClass = configuratorClass.configurableClass
    if configurators.has_key(configurableClass):
        raise ValueError, "class %s already has a Configurator" % configurableClass
    if configurables.has_key(configuratorClass):
        raise ValueError, "configurator %s already registered" % configuratorClass
    theClassHierarchy.registerClass(configuratorClass)
    configurators[configurableClass] = configuratorClass
    configurables[configuratorClass] = configurableClass
    if factory is not None:
        factories[configurableClass] = factory

def hasFactory(configurableClass):
    return factories.has_key(configurableClass)

def getConfigurableClass(configuratorClass):
    return configurables[configuratorClass]

def getConfigurator(instance):
    """Return a configurator for a configurable instance, or None."""
    try:
        klass = instance.__class__
    except AttributeError:
        return None
    try:
        configuratorClass = configurators[klass]
    except KeyError:
        return None
    return configuratorClass(instance)


class InvalidConfiguration(Exception):
    """I am is raised in the case of an invalid configuration.
    """

def createConfigurable(configurableClass, container, name):
    """Instantiate a configurable.

    First, I will find the factory for class configurableClass.
    Then I will call it, with 'container' and 'name' as arguments.
    """
    if not factories.has_key(configurableClass):
        raise TypeError("No configurator registered for %s" % configurableClass)
    return factories[configurableClass](container, name)


class Configurator:
    """A configurator object.

    I have an attribute, configurableClass, which is the class of objects
    I can configure.
    
    I have a dictionary attribute, configTypes, that indicates what sort of
    objects I will allow to be configured.  It is a mapping of variable names
    to a list of [variable type, prompt, description].  Variable types may be
    either python type objects, classes, or objects describing a desired 'hint'
    to the interface (such as 'boolean' or ['choice', 'a', 'b', 'c']). 
    (XXX Still in flux.)

    I have a list attribute, configDispensers, that indicates what methods on
    me may be called with no arguments to create an instance of another
    configurable.  It is a list of the form [(method name, class, descString), ...].
    The class should be a configurator class.
    
    Custom handling of configuration-item-setting can be had by adding
    configure_%s(self, value) methods to my subclass. The default is to set
    an attribute on the instance that will be configured.
    
    A method getConfiguration should return a mapping of attribute to value, for
    attributes mentioned in configTypes. The default is to get the attribute from
    the instance that is being configured.
    
    Specific types of Configurators should form a class heirarchy. For example,
    lets say we have a Domain interface that classes need to implement in order
    to be used in a mail server. We would then make a DomainConfigurator, and
    all Configurators for domains classes should inherit from DomainConfigurator,
    even if the configurable classes do not have a common base class.
    """

    # Change this attribute in subclasses.
    configurableClass = None
    
    configTypes = {}

    configName = None

    configDispensers = []


    def __init__(self, instance):
        """Initialize this configurator with the instance it will be configuring."""
        if not isinstance(instance, self.configurableClass):
            raise TypeError, "%s is not a %s" % (instance, self.configurableClass)
        self.instance = instance

    def getType(self, name):
        """Get the type of a configuration variable."""
        if self.configTypes.has_key(name):
            return self.configTypes[name][0]
        else:
            return None
    
    def configure(self, dict):
        """Set a list of configuration variables.
        """
        items = dict.items()
        
        for name, value in items:
            t = self.getType(name)
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
                setattr(self.instance, name, value)

    def getConfiguration(self):
        """Return a mapping of key/value tuples describing my configuration.
        
        By default gets the attributes from the instance being configured,
        override in subclasses if necessary.
        """
        result = {}
        for k in self.configTypes.keys():
            result[k] = getattr(self.instance, k)
        return result

