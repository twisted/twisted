
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

# DOMWidgets

import traceback
import urllib
from twisted.web.microdom import parseString
from twisted.web import widgets
from twisted.web.woven import model, template

from twisted.python import components, mvc, failure
from twisted.python import domhelpers, log
from twisted.internet import defer

document = parseString("<xml />")

"""
DOMWidgets are views which can be composed into bigger views.
"""

DEBUG = 0


def renderFailure(ignored, request):
    f = failure.Failure()
    log.err(f)
    request.write(widgets.formatFailure(f))
    request.finish()


def _getModel(self):
    if not isinstance(self.model, mvc.Model): # see __class__.doc
         return self.model

    if self.submodel is None:
        if hasattr(self.node, 'toxml'):
            nodeText = self.node.toxml()
        else:
            widgetDict = self.__dict__
        return ""
        raise NotImplementedError, "No model attribute was specified on the node."
    submodelList = self.submodel.split('/')
    currentModel = self.model
    for element in submodelList:
        parentModel = currentModel
        currentModel = currentModel.getSubmodel(element)
        if currentModel is None:
            return None
        adapted = components.getAdapter(currentModel, mvc.IModel, None)
        if adapted is None:
            adapted = model.Wrapper(currentModel)
        #assert adapted is not None, "No IModel adapter registered for %s" % currentModel
        adapted.parent = parentModel
        adapted.name = element
        if isinstance(currentModel, defer.Deferred):
            return adapted
        currentModel = adapted
    return adapted


class Widget(mvc.View):
    """
    A Widget wraps an object, its model, for display. The model can be a
    simple Python object (string, list, etc.) or it can be an instance
    of MVC.Model.  (The former case is for interface purposes, so that
    the rest of the code does not have to treat simple objects differently
    from Model instances.)

    If the model is a Model, there are two possibilities:

       - we are being called to enable an operation on the model
       - we are really being called to enable an operation on an attribute
         of the model, which we will call the submodel
    """
    tagName = None
    def __init__(self, model, submodel = None):
        self.errorFactory = Error
        self.attributes = {}
        mvc.View.__init__(self, model)
        self.become = None
        self.children = []
        self.node = None
        if submodel:
            self.submodel = submodel
        else:
            self.submodel=""
        self.initialize()

    def setId(self, id):
        """
        I use the ID to know which attribute in self.model I am responsible for
        """
        log.msg("setId is deprecated; please use setSubmodel.")
        self.submodel = id

    def setSubmodel(self, submodel):
        """
        I use the submodel to know which attribute in self.model I am responsible for
        """
        self.submodel = submodel

    _getMyModel = _getModel

    def getData(self):
        """
        I have a model; however since I am a widget I am only responsible
        for a portion of that model. This method returns the portion I am
        responsible for.
        """
        currentModel = self._getMyModel()
        if currentModel is None:
            return None
        if hasattr(currentModel, 'getData'):
            return currentModel.getData()
        # Must have been set to a simple type
        return currentModel

    def setData(self, data):
        currentModel = self._getMyModel()
        if currentModel is None:
            raise NotImplementedError, "Can't set the data when there's no model to set it on."
        currentModel.setData(data)

    def add(self, item):
        self.children.append(item)
        
    def insert(self, index, item):
        self.children.insert(index, item)

    def setNode(self, node):
        """
        Set a node for this widget to use instead of creating one programatically.
        Useful for looking up a node in a template and using that.
        """
        self.node = node

    def cleanNode(self, node):
        # Do your part:
        # Prevent infinite recursion
#        if node.hasAttribute('model')
#             node.removeAttribute('model')
        if node.hasAttribute('controller'):
            node.removeAttribute('controller')
        if node.hasAttribute('view'):
            node.removeAttribute('view')
        return node

    def generate(self, request, node):
        data = self.getData()
        if isinstance(data, defer.Deferred):
            data.addCallback(self.setDataCallback, request, node)
            return data
        self.setUp(request, node, data)
        result = self.generateDOM(request, node)
        return result
    
    def setDataCallback(self, result, request, node):
        self.setData(result)
        data = self.getData()
        if isinstance(data, defer.Deferred):
            data.addCallback(self.setDataCallback, request, node)
            data.addErrback(renderFailure, request)
            return data
        self.setUp(request, node, data)
        return self.generateDOM(request, node)
    
    def setUp(self, request, node, data):
        """Override this setUp method to do any work your widget
        needs to do prior to rendering.
        
        data is the Model data this Widget is meant to operate upon.
        
        Overriding this method deprecates overriding generateDOM directly.
        """
        pass
    
    def generateDOM(self, request, node):
        if DEBUG:
            template = node.toxml()
            log.msg(template)
        if self.tagName and str(node.tagName) != self.tagName:
            parent = node.parentNode
            node = document.createElement(self.tagName)
            node.parentNode = parent
        else:
            parentNode = node.parentNode
            node.parentNode = None
            new = node.cloneNode(1)
            node.parentNode = parentNode
            node = self.cleanNode(new)
        for key, value in self.attributes.items():
            node.setAttribute(key, value)
        for item in self.children:
            if hasattr(item, 'generateDOM'):
                item = item.generateDOM(request, node)
            node.appendChild(item)
        if self.become is None:
            self.node = node
        else:
            become = self.become
            self.become = None
            become.add(self)
            self.node = become.generateDOM(request, node)
        return self.node

    def __setitem__(self, item, value):
        self.attributes[item] = value
    
    def __getitem__(self, item):
        return self.attributes[item]

    def setError(self, request, message):
        self.become = self.errorFactory(self.model, message)

    def initialize(self):
        pass


class Text(Widget):
    def __init__(self, text, raw=0):
        self.raw = raw
        if isinstance(text, mvc.Model):
            Widget.__init__(self, text)
        else:
            Widget.__init__(self, mvc.Model())
        self.text = text
    
    def generateDOM(self, request, node):
        if isinstance(self.text, mvc.Model):
            if self.raw:
                textNode = domhelpers.RawText(str(self.getData()))
            else:
                textNode = document.createTextNode(str(self.getData()))
            if node is None:
                return textNode
            node.appendChild(textNode)
            return node
        else:
            if self.raw:
                return domhelpers.RawText(self.text)
            else:
                return document.createTextNode(self.text)


class WidgetNodeMutator(template.NodeMutator):
    def generate(self, request, node):
        newNode = self.data.generate(request, node)
        if isinstance(newNode, defer.Deferred):
            return newNode
        nodeMutator = template.NodeNodeMutator(newNode)
        nodeMutator.d = self.d
        return nodeMutator.generate(request, node)


components.registerAdapter(WidgetNodeMutator, Widget, template.INodeMutator)


class Image(Text):
    tagName = 'img'
    def generateDOM(self, request, node):
        if isinstance(self.text, mvc.Model):
            data = self.getData()
        else:
            data = self.text
        node = Widget.generateDOM(self, request, node)
        node.setAttribute('src', data)
        return node


class Error(Widget):
    tagName = 'span'
    def __init__(self, model, message=""):
        Widget.__init__(self, model)
        self.message = message
    
    def generateDOM(self, request, node):
        self['style'] = 'color: red'
        self.add(Text(" " + self.message))
        return Widget.generateDOM(self, request, node)


class Div(Widget):
    tagName = 'div'

class Span(Widget):
    tagName = 'span'

class Br(Widget):
    tagName = 'br'

class Input(Widget):
    tagName = 'input'    
    def setSubmodel(self, submodel):
        self.submodel=submodel
        self['name'] = submodel

    def generateDOM(self, request, node):
        mVal = self.getData()
        if mVal:
            self['value'] = str(mVal)
        return Widget.generateDOM(self, request, node)

class CheckBox(Input):
    def initialize(self):
        self['type'] = 'checkbox'

class RadioButton(Input):
    def initialize(self):
        self['type'] = 'radio'

class File(Input):
    def initialize(self):
        self['type'] = 'file'

class Hidden(Input):
    def initialize(self):
        self['type'] = 'hidden'

class InputText(Input):
    def initialize(self):
        self['type'] = 'text'

class PasswordText(Input):
    """
    I render a password input field.
    """
    def initialize(self):
        self['type'] = 'password'

class Button(Input):
    def initialize(self):
        self['type'] = 'button'

class Select(Input):
    tagName = 'select'

class Option(Input):
    tagName = 'option'
    def generateDOM(self, request, node):
        self.add(Text(self.getData()))
        return Input.generateDOM(self, request, node)

class Anchor(Widget):
    tagName = 'a'
    def initialize(self):
        self.baseHREF = ''
        self.parameters = {}
        self.raw = 0
    
    def setRaw(self, raw):
        self.raw = raw

    def setLink(self, href):
        self.baseHREF= href
    
    def setParameter(self, key, value):
        self.parameters[key] = value

    def generateDOM(self, request, node):
        href = self.baseHREF
        params = urllib.urlencode(self.parameters)
        if params:
            href = href + '?' + params
        self['href'] = href or self.getData() + '/'
        data = self.getData()
        if data is None:
            data = ""
        self.add(Text(data, self.raw))
        return Widget.generateDOM(self, request, node)

class List(Widget):
    """
    I am a widget which knows how to generateDOM for a python list.

    A List should be specified in the template HTML as so:

       | <ul id="blah" view="List">
       |     <li id="emptyList">This will be displayed if the list is empty.</li>
       |     <li id="listItem" view="Text">Foo</li>
       | </ul>

    If you have nested lists, you may also do something like this:

       | <table model="blah" view="List">
       |     <tr class="listHeader"><th>A</th><th>B</th></tr>
       |     <tr class="emptyList"><td colspan='2'>***None***</td></tr>
       |     <tr class="listItem">
       |         <td><span view="Text" model="1" /></td>
       |         <td><span view="Text" model="2" /></td>
       |     </tr>
       |     <tr class="listFooter"><td colspan="2">All done!</td></tr>
       | </table>

    Where blah is the name of a list on the model; eg:                          

       | self.model.blah = ['foo', 'bar']

    """
    tagName = None
    def generateDOM(self, request, node):
        node = Widget.generateDOM(self, request, node)
        listHeader = domhelpers.getIfExists(node, 'listHeader')
        listFooter = domhelpers.getIfExists(node, 'listFooter')
        emptyList = domhelpers.getIfExists(node, 'emptyList')
        # xxx with this implementation all elements of the list must use the same view widget
        listItems = domhelpers.locateNodes(node, 'itemOf', self.submodel.split('/')[-1])
        if not listItems:
            listItems = [domhelpers.get(node, 'listItem')]
        domhelpers.clearNode(node)
        if not listHeader is None:
            node.appendChild(listHeader)
        submodel = self.submodel
        data = self.getData()
        currentListItem = 0
        if len(data):
            for itemNum in range(len(data)):
                # theory: by appending copies of the li node
                # each node will be handled once we exit from
                # here because handleNode will then recurse into
                # the newly appended nodes

                newNode = listItems[currentListItem].cloneNode(1)
                if currentListItem >= len(listItems) - 1:
                    currentListItem = 0
                else:
                    currentListItem += 1

                domhelpers.superAppendAttribute(newNode, '_submodel_prefix', self.submodel)
                domhelpers.superAppendAttribute(newNode, '_submodel_prefix', str(itemNum))
                node.appendChild(newNode)
                newNode.parentNode = node
        elif not emptyList is None:
            node.appendChild(emptyList)
        if not listFooter is None:
            node.appendChild(listFooter)
        return node

class ColumnList(List):
    def __init__(self, model, columns=1, start=0, end=0):
        List.__init__(self, model)
        self.columns = columns
        self.start = start
        self.end = end

    def setColumns(self, columns):
        self.columns = columns

    def setStart(self, start):
        self.start = start
    
    def setEnd(self, end):
        self.end = end

    def generateDOM(self, request, node):
        node = Widget.generateDOM(self, request, node)
        listRow = domhelpers.get(node, 'listRow')
        listItem = domhelpers.get(listRow, 'listItem')
        domhelpers.clearNode(node)
        domhelpers.clearNode(listRow)
        
        if self.end:
            listSize = self.end - self.start
            if listSize > len(self.getData()):
                listSize = len(self.getData())
        else:
            listSize = len(self.getData())
        for itemNum in range(listSize):
            if itemNum % self.columns == 0:
                row = listRow.cloneNode(1)
                node.appendChild(row)
            newNode = listItem.cloneNode(1)
            domhelpers.superAppendAttribute(newNode, '_submodel_prefix', self.submodel)
            domhelpers.superAppendAttribute(newNode, '_submodel_prefix', str(itemNum + self.start))
            row.appendChild(newNode)
        return node
        
class Bold(Widget):
    tagName = 'b'
    
class Table(Widget):
    tagName = 'table'

class Row(Widget):
    tagName = 'tr'

class Cell(Widget):
    tagName = 'td'

class RawText(Widget):
    def generateDOM(self, request, node):
        self.node = domhelpers.RawText(self.getData())
        return self.node

