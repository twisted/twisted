# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
from twisted.web import server, resource, microdom, domhelpers
from twisted.protocols import http
from twisted.test import test_web
from twisted.internet import reactor, defer

from twisted.web.woven import template, model, view, controller, widgets, input


# Reusable test harness

class WovenTC(unittest.TestCase):
    modelFactory = lambda self: None
    resourceFactory = None
    def setUp(self):
        self.m = self.modelFactory()
        self.t = self.resourceFactory(self.m)
        self.r = test_web.DummyRequest([])
        self.prerender()
        self.t.render(self.r, block=1)
        
        self.output = ''.join(self.r.written)
#        print self.output
        self.d = microdom.parseString(self.output)
    
    def prerender(self):
        pass

# Test 1
# Test that replacing nodes with a string works properly


class SimpleTemplate(template.DOMTemplate):
    template = """<http>
    <head>
        <title id="title"><span view="getTitle">Hello</span></title>
    </head>
    <body>
        <h3 id="hello"><span view="getHello">Hi</span></h3>
    </body>
</http>"""
    
    def factory_getTitle(self, request, node):
        return "Title"
    
    def factory_getHello(self, request, node):
        return "Hello"

class DOMHelpersTest(unittest.TestCase):
    def testMicrodom(self):
        d = microdom.parseString("<x id='hello' />")
        helloNode = d.getElementById("hello")
        self.failUnlessEqual(helloNode, d.documentElement)


class DOMTemplateTest(WovenTC):
    resourceFactory = SimpleTemplate
    def testSimpleRender(self):
        titleNode = self.d.getElementById("title")
        helloNode = self.d.getElementById("hello")
        
        assert domhelpers.gatherTextNodes(titleNode) == 'Title'
        assert domhelpers.gatherTextNodes(helloNode) == 'Hello'


# Test 2
# Test just like the first, but with Text widgets

class TemplateWithWidgets(SimpleTemplate):
    def factory_getTitle(self, request, node):
        return widgets.Text("Title")

    def factory_getHello(self, request, node):
        return widgets.Text("Hello")


class TWWTest(DOMTemplateTest):
    resourceFactory = TemplateWithWidgets


# Test 3
# Test a fancier widget, and controllers handling submitted input


class MDemo(model.Model):
    foo = "Hello world"
    color = 'blue'


class FancyBox(widgets.Widget):
    def setUp(self, request, node, data):
        self['style'] = 'margin: 1em; padding: 1em; background-color: %s' % data


class VDemo(view.View):
    template = """<html>

<div id="box" model="color" view="FancyBox"><h1 model="foo" view="Text" /></div>

<form action="">
Type a color and hit submit:
<input type="text" controller="change" model="color" name="color" />
<input type="submit" />
</form>

</html>
"""
    def wvfactory_FancyBox(self, request, node, model):
        return FancyBox(model)
    
    def renderFailure(self, failure, request):
        return failure


class ChangeColor(input.Anything):
    def commit(self, request, node, data):
        session = request.getSession()
        session.color = data


class CDemo(controller.Controller):
    def setUp(self, request):
        session = request.getSession()
        self.model.color = getattr(session, 'color', self.model.color)

    def factory_change(self, request, node, model):
        return ChangeColor(model)


view.registerViewForModel(VDemo, MDemo)
controller.registerControllerForModel(CDemo, MDemo)


class ControllerTest(WovenTC):
    modelFactory = MDemo
    resourceFactory = CDemo
    
    def prerender(self):
        self.r.addArg('color', 'red')
    
    def testControllerOutput(self):
        boxNode = self.d.getElementById("box")
        style = boxNode.getAttribute("style")
        styles = style.split(";")
        sDict = {}
        for item in styles:
            key, value = item.split(":")
            key = key.strip()
            value = value.strip()
            sDict[key] = value
        
#         print sDict
        assert sDict['background-color'] == 'red'


# Test 4
# Test a list, a list widget, and Deferred data handling

identityList = ['asdf', 'foo', 'fredf', 'bob']

class MIdentityList(model.Model):
    def __init__(self):
        model.Model.__init__(self)
        self.identityList = defer.Deferred()
        self.identityList.callback(identityList)


class VIdentityList(view.View):
    template = """<html>
    <ul id="list" view="identityList" model="identityList">
        <li itemOf="identityList">
            <span view="text" />
        </li>
    </ul>
</html>"""

    def wvfactory_identityList(self, request, node, model):
        return widgets.List(model)

    def wvfactory_text(self, request, node, model):
        return widgets.Text(model)

    def renderFailure(self, failure, request):
        return failure


class CIdentityList(controller.Controller):
    pass


view.registerViewForModel(VIdentityList, MIdentityList)
controller.registerControllerForModel(CIdentityList, MIdentityList)


class ListDeferredTest(WovenTC):
    modelFactory = MIdentityList
    resourceFactory = CIdentityList

    def testOutput(self):
        listNode = self.d.getElementById("list")
        liNodes = domhelpers.getElementsByTagName(listNode, 'li')
        assert len(liNodes) == len(identityList)


# Test 5
# Test nested lists

class LLModel(model.Model):
    data = [['foo', 'bar', 'baz'],
            ['gum', 'shoe'],
            ['ggg', 'hhh', 'iii']
           ]


class LLView(view.View):
    template = """<html>
    <ul id="first" view="List" model="data">
        <li slot="listItem">
            <ol view="List">
                <li slot="listItem" view="Text" />
            </ol>
        </li>
    </ul>
</html>"""

    def wvfactory_List(self, request, node, model):
        return widgets.List(model)


class NestedListTest(WovenTC):
    modelFactory = LLModel
    resourceFactory = LLView
    
    def testOutput(self):
        listNode = self.d.getElementById("first")
        liNodes = filter(lambda x: hasattr(x, 'tagName') and x.tagName == 'li', listNode.childNodes)
#        print len(liNodes), len(self.m.data), liNodes, self.m.data
        assert len(liNodes) == len(self.m.data)
        for i in range(len(liNodes)):
            sublistNode = domhelpers.getElementsByTagName(liNodes[i], 'ol')[0]
            subLiNodes = domhelpers.getElementsByTagName(sublistNode, 'li')
            assert len(self.m.data[i]) == len(subLiNodes)


view.registerViewForModel(LLView, LLModel)

testCases = [DOMTemplateTest, TWWTest, ControllerTest, ListDeferredTest, NestedListTest]
  
