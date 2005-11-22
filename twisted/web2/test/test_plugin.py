from twisted.trial import unittest
from twisted.web2 import resource, http
from twisted.web2 import plugin

class MyDefaultResource(plugin.PluginResource):
    def render(self, req):
        http.Response(200, stream='DEFAULT')

class TestResourcePlugin(unittest.TestCase):
    def testResource(self):
        assert isinstance(plugin.resourcePlugger('TestResource'),
                          plugin.TestResource)

    def testResourceArguments(self):
        myPluggedResource = plugin.resourcePlugger('TestResource',
                                            'Foo', bar='Bar')
        
        assert isinstance(myPluggedResource, plugin.TestResource)

        self.assertEquals(myPluggedResource.foo, 'Foo')
        self.assertEquals(myPluggedResource.bar, 'Bar')
           
    def testNoPlugin(self):
        myPluggedResource = plugin.resourcePlugger('NoSuchResource')
        
        assert isinstance(myPluggedResource, plugin.NoPlugin)
        
        self.assertEquals(myPluggedResource.plugin, 'NoSuchResource')

    def testDefaultPlugin(self):
        myPluggedResource = plugin.resourcePlugger('NoSuchResource',
                                                   defaultResource=MyDefaultResource)

        assert isinstance(myPluggedResource, MyDefaultResource)
