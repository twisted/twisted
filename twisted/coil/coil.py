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

# Twisted Imports
from twisted.python import log, components, reflect, roots


class InvalidConfiguration(Exception):
    """I am is raised in the case of an invalid configuration.
    """

# map between classes and their factories
factories = {}
# map between interfaces and a list of classes implementing them
interfaceImplementors = {}


# methods for coil

def registerConfigurator(configuratorClass, factory=None):
    """Register a configurator for a class."""
    configurableClass = configuratorClass.configurableClass
    components.registerAdapter(configuratorClass, configurableClass, IConfigurator)
    if factory is not None:
        registerFactory(configurableClass, factory)

def registerFactory(configurableClass, factory):
    """Register a factory for a class."""
    factories[configurableClass] = factory
    for i in components.getInterfaces(configurableClass):
        if interfaceImplementors.has_key(i):
            interfaceImplementors[i].append(configurableClass)
        else:
            interfaceImplementors[i] = [configurableClass]

def hasFactory(configurableClass):
    """Check if factory is available for this class."""
    return factories.has_key(configurableClass)

def createConfigurable(configurableClass, container, name):
    """Instantiate a configurable.

    First, I will find the factory for class configurableClass.
    Then I will call it, with 'container' and 'name' as arguments.
    """
    if not factories.has_key(configurableClass):
        raise TypeError("No configurator registered for %s" % configurableClass)
    return factories[configurableClass](container, name)

def getCollection(obj):
    """Get an object implementing ICollection for obj."""
    if components.implements(obj, IConfigurator):
        obj = obj.getInstance()
    return components.getAdapter(obj, ICollection, None)

def getConfigurator(obj):
    """Get an object implement IConfigurator for obj."""
    return components.getAdapter(obj, IConfigurator, None)

def getConfiguratorClass(klass):
    """Return an IConfigurator class for given class."""
    return components.getAdapterClass(klass, IConfigurator, None)

def getImplementors(interface):
    """Return list of registered classes that implement an interface."""
    return interfaceImplementors.get(interface, [])

def getConfiguratorsForTree(root):
    """Return iterator of Configurators for a config tree.

    This really ought to be implemented as a generator.
    """
    stack = [root]
    result = []

    while stack:
        obj = stack.pop()

        # add the configurator's dispensers to result
        cfg = getConfigurator(obj)
        if cfg is not None: result.append(cfg)

        # see if obj has children and if so add them to stack
        collection = getCollection(obj)
        if collection is not None:
            for name, entity in collection.listStaticEntities():
                stack.append(entity)

    return result


# interfaces for coil

class IConfigurator(components.Interface):
    """A configurator object.

    I have an attribute, configurableClass, which is the class of objects
    I can configure.

    I have a dictionary attribute, configTypes, that indicates what sort of
    objects I will allow to be configured.  It is a mapping of variable names
    to a list of [variable type, prompt, description].  Variable types may be
    either python type objects, classes, or objects describing a desired 'hint'
    to the interface (such as 'boolean' or ['choice', 'a', 'b', 'c']).
    (XXX Still in flux.)
    """

    def getInstance(self):
        """Return instance being configured."""
        raise NotImplementedError

    def getType(self, name):
        """Get the type of a configuration variable."""
        raise NotImplementedError

    def configDispensers(self):
        """Indicates what methods on me may be called with no arguments to create
        an instance of another configurable.  It returns a list of the form
        [(method name, interface, descString), ...].
        """
        raise NotImplementedError

    def configure(self, dict):
        """Configure our instance, given a dict of properties.

        Will raise a InvalidConfiguration exception on bad input.
        """
        raise NotImplementedError

    def getConfiguration(self):
        """Return a mapping of attribute to value.

        The returned key are the attributes mentioned in configTypes.
        """
        raise NotImplementedError


class ICollection(components.Interface):
    """A collection for coil."""


class IStaticCollection(ICollection):
    """A coil collection to which we can't add items."""

    def listStaticEntities(self):
        """Return list of children."""
        raise NotImplementedError

    def getStaticEntity(self, name):
        """Return a child given its name."""
        raise NotImplementedError


class IConfigCollection(ICollection):
    """A coil collection to which objects can be added.

    Must have an attribute entityType, which is either an Interface
    which added objects must implement, or a StringType, IntType or FloatType.
    """


# utility classes for coil

class Configurator:
    """A configurator object implementing default behaviour.

    Custom handling of configuration-item-setting can be had by adding
    configure_%s(self, value) methods to my subclass. The default is to set
    an attribute on the instance that will be configured.

    A method getConfiguration should return a mapping of attribute to value, for
    attributes mentioned in configTypes. The default is to get the attribute from
    the instance that is being configured.
    """

    __implements__ = IConfigurator

    # Change this attribute in subclasses.
    configurableClass = None

    configTypes = {}

    configName = None

    def __init__(self, instance):
        """Initialize this configurator with the instance it will be configuring."""
        if not isinstance(instance, self.configurableClass):
            raise TypeError, "%s is not a %s" % (instance, self.configurableClass)
        self.instance = instance

    def configDispensers(self):
        """Return list of dispensers."""
        return []

    def getInstance(self):
        """Return the instance being configured."""
        return self.instance

    def getType(self, name):
        """Get the type of a configuration variable."""
        if self.configTypes.has_key(name):
            return self.configTypes[name][0]
        else:
            return None

    def configure(self, dict):
        """Set a list of configuration variables."""
        items = dict.items()

        for name, value in items:
            t = self.getType(name)
            if isinstance(t, types.TypeType):
                if not isinstance(value, t) or (value is None):
                    raise InvalidConfiguration("type mismatch")
            elif isinstance(t, types.ClassType) and issubclass(t, components.Interface):
                if not components.implements(value, t) or (value is None):
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


class StaticCollection(roots.Locked):
    """A roots.Locked that implement IStaticCollection."""

    __implements__ = IStaticCollection


class ConfigCollection(roots.Constrained):
    """A default implementation of IConfigCollection."""

    __implements__ = IConfigCollection

    # override in subclasses
    entityType = components.Interface

    def entityConstraint(self, entity):
        if isinstance(self.entityType, types.TypeType) and isinstance(entity, self.entityType):
            return 1
        elif components.implements(entity, self.entityType):
            return 1
        else:
            raise roots.ConstraintViolation("%s of incorrect type (%s)" %
                                      (entity, self.entityType))

    def getNameType(self):
        return "Name"

    def getEntityType(self):
        return self.entityType.__name__


class CollectionWrapper:
    """Wrap an existing roots.Collection as a IConfigCollection."""

    __implements__ = IConfigCollection

    def __init__(self, collection):
        self._collection = collection

    def __getattr__(self, attr):
        return getattr(self._collection, attr)


class DispenserStorage:
    """A mini-database of dispensers.

    When first created, traverses the tree of configcollections and
    configurators and loads all dispensers.
    """

    def __init__(self, root):
        # self.dispensers is a mapping:
        # <interface> --> <list of (instance, functionName, description) tuples>
        #
        # The functionName is a string, the name of a method of the configurator
        # for the given instance.
        self.dispensers = {}
        self.addObject(root)

    def addObject(self, object):
        """Add the dispensers for an object and its config children."""
        dispensers = self.dispensers

        for cfg in getConfiguratorsForTree(object):
            obj = cfg.getInstance()
            for funcName, interface, desc in cfg.configDispensers():
                if not dispensers.has_key(interface): dispensers[interface] = []
                dispensers[interface].append((obj, funcName, desc))

    def removeObject(self, object):
        """Remove an object and its config children."""
        dispensers = self.dispensers

        for cfg in getConfiguratorsForTree(object):
            obj = cfg.getInstance()
            for funcName, interface, desc in cfg.configDispensers():
                if dispensers.has_key(interface):
                    dispensers[interface].remove((obj, funcName, desc))
                if not dispensers[interface]:
                    del dispensers[interface]

    def getDispensers(self, interface):
        """Return a list of dispensers for a given interface.

        List items are in the form (instance, functionName, description).
        """
        return self.dispensers.get(interface, [])
