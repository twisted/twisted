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

from pyunit import unittest

from twisted.coil import coil
from twisted.python import components

import types

class MyConfigurable:

    foo = 1
    bar = "hello"

def myFactory(container, name):
    return MyConfigurable()

class MyConfig(coil.Configurator):
    
    configurableClass = MyConfigurable
    configTypes = {
        "foo": [types.IntType, "Foo", "Put your face in the foo."],
        "bar": [types.StringType, "Bar", "A bar of stuff."]
        }

class IFoo(components.Interface):
    pass

class IBar(IFoo):
    pass

class CustomConfigurable:
    
    __implements__ = IBar
    
    def __init__(self, name):
        self.name = name
        self.foo = "bzzt"

def customFactory(container, name):
    return CustomConfigurable(name)

class CustomConfig(coil.Configurator):

    configurableClass = CustomConfigurable
    
    configTypes = {
        "foo": [types.StringType, "Foo", "Foo is good for you."]
    }
    
    def config_foo(self, foo):
        self.instance.foo = 2 * foo

coil.registerConfigurator(CustomConfig, customFactory)


class CoilTest(unittest.TestCase):
    
    def testConfigurable(self):
        o = MyConfigurable()
        c = MyConfig(o)
        c.configure({'foo':1, 'bar':'hi'})
        self.assertEquals(o.foo, 1)
        self.assertEquals(o.bar, 'hi')
        self.assertEquals(c.getConfiguration(), {'foo':1, 'bar':'hi'})
        self.failUnlessRaises(coil.InvalidConfiguration,
                              c.configure, {'foo':'hi'})
        self.failUnlessRaises(coil.InvalidConfiguration,
                              c.configure, {'bar':1})
        self.assertEquals(c.getInstance(), o)

    def testCustomConfigurable(self):
        c = coil.createConfigurable(CustomConfigurable, None, "testName")
        self.assertEquals(c.name, "testName")
        config = coil.getConfigurator(c)
        config.configure({'foo' : 'test'})
        self.assertEquals(c.foo, 'testtest')
    
    def testRegistration(self):
        self.assertEquals(CustomConfig, coil.getConfiguratorClass(CustomConfigurable))
        self.assert_(coil.hasFactory(CustomConfigurable))
        self.assertEquals(coil.getImplementors(IFoo), [CustomConfigurable])
        self.assertEquals(coil.getImplementors(IBar), [CustomConfigurable])
