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

"""Component architecture for Twisted."""


class Interface:
    """Base class for interfaces.
    
    Interfaces define and document an interface for a class. An interface
    class's name must begin with I, and all its methods must raise 
    NotImplementedError, to show they are abstract.
    
    A class that implements an interface should list the interfaces it
    implements in a class-level list, __implements__.
    
    For example::
    
        | class IAdder(Interface):
        |     "Objects implementing this interface can add objects."
        | 
        |     def add(self, a, b):
        |         "Add two objects together and return the result."
        |         raise NotImplementedError
        |
        | class Adder:
        | 
        |     __implements__ = [IAdder]
        |     
        |     def add(self, a, b):
        |         return a + b
    
    """


def implements(obj, interfaceClass):
    """Return boolean indicating if obj implements the given interface."""
    if not hasattr(obj, '__class__'):
        return 0
    
    return classImplements(obj.__class__, interfaceClass)


def classImplements(klass, interfaceClass):
    """Return boolean indicating if class implements the given interface."""
    if not hasattr(klass, '__implements__'):
        return 0
    
    for i in klass.__implements__:
        if issubclass(i, interfaceClass):
            return 1
    
    return 0


# mapping between (<class>, <interface>) and <adapter class>
adapterRegistry = {}


def registerAdapter(adapterClass, origClass, interfaceClass):
    """Register an adapter class.
    
    An adapter class is expected to implement the given interface, by
    adapting instances of paramter 'origClass'. An adapter class's
    __init__ method should accept one parameter, an instance of 'origClass'.
    """
    if adapterRegistry.has_key((origClass, interfaceClass)):
        raise ValueError, "an adapter was already registered."
    
    if not classImplements(adapterClass, interfaceClass):
        raise ValueError, "%s doesn't implement interface %s" % (adapterClass, interfaceClass)
    
    if not issubclass(interfaceClass, Interface):
        raise ValueError, "interface %s doesn't inherit from %s" % (interfaceClass, Interface)
    
    adapterRegistry[(origClass, interfaceClass)] = adapterClass


def getAdapter(obj, interfaceClass, default):
    """Return an object that implements the given interface.
    
    The result will be a wrapper around the object passed as a paramter, or
    the parameter itself if it already implements the interface. If no
    adapter can be found, the 'default' parameter will be returned.
    """
    if not hasattr(obj, '__class__'):
        raise TypeError, "%s is not an instance" % obj
    
    if implements(obj, interfaceClass):
        return obj
    
    adapterClass = adapterRegistry.get((obj.__class__, interfaceClass), None)
    if adapterClass is None:
        return default
    else:
        return adapterClass(obj)
