
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

import urllib
from twisted.web.microdom import parseString


#sibling imports
import model
import template
import view
import utils

from twisted.python import components, failure
from twisted.python import domhelpers, log
from twisted.internet import defer

document = parseString("<xml />")

"""
DOMWidgets are views which can be composed into bigger views.
"""

DEBUG = 0


class Widget(view.View):
    """
    A Widget wraps an object, its model, for display. The model can be a
    simple Python object (string, list, etc.) or it can be an instance
    of L{model.Model}.  (The former case is for interface purposes, so that
    the rest of the code does not have to treat simple objects differently
    from Model instances.)

    If the model is-a Model, there are two possibilities:

       - we are being called to enable an operation on the model
       - we are really being called to enable an operation on an attribute
         of the model, which we will call the submodel

    @cvar tagName: The tag name of the element that this widget creates. If this
          is None, then the original Node will be cloned.
    @cvar wantsAllNotifications: Indicate that this widget wants to recieve every
          change notification from the main model, not just notifications that affect
          it's model.
    @ivar model: If the current model is an L{model.Model}, then the result of
          model.getData(). Otherwise the original object itself.
    """

    wantsAllNotifications = 0

    tagName = None
    def __init__(self, model, submodel = None):
        self.errorFactory = Error
        self.attributes = {}
        view.View.__init__(self, model)
        self.become = None
        self.children = []
        self.node = None
        self.templateNode = None
        if submodel:
            self.submodel = submodel
        else:
            self.submodel=""
        self.initialize()

    def initialize(self):
        """
        Use this method instead of __init__ to initialize your Widget, so you
        don't have to deal with calling the __init__ of the superclass.
        """
        pass


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

    _getMyModel = utils._getModel

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
        """
        Add `item' to the children of the resultant DOM Node of this widget.
        
        @type item: A DOM node or L{Widget}.
        """
        self.children.append(item)
        
    def insert(self, index, item):
        """
        Insert `item' at `index' in the children list of the resultant DOM Node
        of this widget.
        
        @type item: A DOM node or L{Widget}.
        """
        self.children.insert(index, item)

    def setNode(self, node):
        """
        Set a node for this widget to use instead of creating one programatically.
        Useful for looking up a node in a template and using that.
        """
        # self.templateNode should always be the original, unmutated
        # node that was in the HTML template.
        if self.templateNode == None:
            self.templateNode = node
        self.node = node

    def cleanNode(self, node):
        """
        Do your part, prevent infinite recursion!
        """
        #if node.hasAttribute('model')
        #    node.removeAttribute('model')
        
        if node.hasAttribute('controller'):
            node.removeAttribute('controller')
        if node.hasAttribute('view'):
            node.removeAttribute('view')
        return node

    def generate(self, request, node):
        data = self.getData()
        if isinstance(data, defer.Deferred):
            data.addCallback(self.setDataCallback, request, node)
            data.addErrback(utils.renderFailure, request)
            return data
        self.setUp(request, node, data)
        # generateDOM should always get a reference to the
        # templateNode from the original HTML
        result = self.generateDOM(request, self.templateNode)
        return result
    
    def setDataCallback(self, result, request, node):
        self.setData(result)
        data = self.getData()
        if isinstance(data, defer.Deferred):
            data.addCallback(self.setDataCallback, request, node)
            data.addErrback(utils.renderFailure, request)
            return data
        self.setUp(request, node, data)
        # generateDOM should always get a reference to the
        # templateNode from the original HTML
        return self.generateDOM(request, self.templateNode)
    
    def setUp(self, request, node, data):
        """
        Override this method to set up your Widget prior to generateDOM. This
        is a good place to call methods like L{add}, L{insert}, L{__setitem__}
        and L{__getitem__}.
        
        Overriding this method obsoletes overriding generateDOM directly, in
        most cases.

        @type request: L{twisted.web.server.Request}.
        @param node: The DOM node which this Widget is operating on.
        @param data: The Model data this Widget is meant to operate upon.
        """
        pass
    
    def generateDOM(self, request, node):
        """
        @returns: A DOM Node to replace the Node in the template that this
                  Widget handles. This Node is created based on L{tagName},
                  L{children}, and L{attributes} (You should populate these
                  in L{setUp}, probably).
        """
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

    def modelChanged(self, payload):
        request = payload['request']
        oldNode = self.node
        if payload.has_key(self.submodel):
            data = payload[self.submodel]
        else:
            data = self.getData()
        self.children = []
        # generateDOM should always get a reference to the
        # templateNode from the original HTML
        self.setUp(request, self.templateNode, data)
        newNode = self.generateDOM(request, self.templateNode)
        mutator = template.NodeNodeMutator(newNode)
        mutator.d = request.d
        mutator.generate(request, oldNode)
        self.node = newNode
        return newNode
    
    def __setitem__(self, item, value):
        """
        Convenience syntax for adding attributes to the resultant DOM Node of
        this widget.
        """
        self.attributes[item] = value
    
    def __getitem__(self, item):
        """
        Convenience syntax for getting an attribute from the resultant DOM Node
        of this widget.
        """
        return self.attributes[item]

    def setError(self, request, message):
        """
        Convenience method for allowing a Controller to report an error to the
        user. When this is called, a Widget of class self.errorFactory is instanciated
        and set to self.become. When generate is subsequently called, self.become
        will be responsible for mutating the DOM instead of this widget.
        """
        self.become = self.errorFactory(self.model, message)


class DefaultWidget(Widget):
    def generate(self, request, node):
        """
        By default, we just return the node unchanged
        """
        return node

class WidgetNodeMutator(template.NodeMutator):
    """
    XXX: Document
    """
    def generate(self, request, node):
        newNode = self.data.generate(request, node)
        if isinstance(newNode, defer.Deferred):
            return newNode
        nodeMutator = template.NodeNodeMutator(newNode)
        nodeMutator.d = self.d
        return nodeMutator.generate(request, node)

components.registerAdapter(WidgetNodeMutator, Widget, template.INodeMutator)


class Text(Widget):
    """
    A simple Widget that renders some text.
    """
    def __init__(self, text, raw=0):
        """
        @param text: The text to render.
        @type text: A string or L{model.Model}.
        @ivar raw: A boolean that specifies whether to render the text as
              a L{domhelpers.RawText} or as a DOM TextNode.
        """
        self.raw = raw
        if isinstance(text, model.Model):
            Widget.__init__(self, text)
        else:
            Widget.__init__(self, model.Model())
        self.text = text
    
    def generateDOM(self, request, node):
        if isinstance(self.text, model.Model):
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

class Image(Text):
    """
    A simple Widget that creates an `img' tag.
    """
    tagName = 'img'
    def generateDOM(self, request, node):
        #`self.text' is lame, perhaps there should be a DataWidget that Text
        #and Image both subclass.
        if isinstance(self.text, model.Model):
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
        self.submodel = submodel
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
        self.text = ''
    
    def setRaw(self, raw):
        self.raw = raw

    def setLink(self, href):
        self.baseHREF= href
    
    def setParameter(self, key, value):
        self.parameters[key] = value

    def setText(self, text):
        self.text = text

    def generateDOM(self, request, node):
        href = self.baseHREF
        params = urllib.urlencode(self.parameters)
        if params:
            href = href + '?' + params
        data = self.getData()
        self['href'] = href or data + '/'
        if data is None:
            data = ""
        self.add(Text(self.text or data, self.raw))
        return Widget.generateDOM(self, request, node)

class List(Widget):
    """
    I am a widget which knows how to generateDOM for a python list.

    A List should be specified in the template HTML as so::

       | <ul model="blah" view="List">
       |     <li id="emptyList">This will be displayed if the list
       |         is empty.</li>
       |     <li id="listItem" view="Text">Foo</li>
       | </ul>

    If you have nested lists, you may also do something like this::

       | <table model="blah" view="List">
       |     <tr class="listHeader"><th>A</th><th>B</th></tr>
       |     <tr class="emptyList"><td colspan='2'>***None***</td></tr>
       |     <tr class="listItem">
       |         <td><span view="Text" model="1" /></td>
       |         <td><span view="Text" model="2" /></td>
       |     </tr>
       |     <tr class="listFooter"><td colspan="2">All done!</td></tr>
       | </table>

    Where blah is the name of a list on the model; eg::             

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
        data = self.getData()
        if self._has_data(data):
            self._iterateData(node, listItems, self.submodel, data)
        elif not emptyList is None:
            node.appendChild(emptyList)
        if not listFooter is None:
            node.appendChild(listFooter)
        return node

    def _has_data(self, data):
        return len(data)

    def _iterateData(self, parentNode, listItems, submodel, data):
        currentListItem = 0
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
            modelName = submodel.split('/')[-1]
            domhelpers.superAppendAttribute(newNode, '_submodel_prefix',
                                            modelName)
            domhelpers.superAppendAttribute(newNode, '_submodel_prefix',
                                            str(itemNum))
            parentNode.appendChild(newNode)

class KeyedList(List):
    """
    I am a widget which knows how to display the values stored within a
    Python dictionary..

    A KeyedList should be specified in the template HTML as so::

       | <ul model="blah" view="List">
       |     <li id="emptyList">This will be displayed if the list is
       |         empty.</li>
       |     <li id="listItem" view="Text">Foo</li>
       | </ul>

    I can take advantage of C{listHeader}, C{listFooter} and C{emptyList}
    items just as a L{List} can.
    """
    def _has_data(self, data):
        return len(data.keys())

    def _iterateData(self, parentNode, listItems, submodel, data):
        """
        """
        currentListItem = 0
        for key in data.keys():
            newNode = listItems[currentListItem].cloneNode(1)
            if currentListItem >= len(listItems) - 1:
                currentListItem = 0
            else:
                currentListItem += 1
            
            modelName = submodel.split('/')[-1]
            domhelpers.superAppendAttribute(newNode, '_submodel_prefix',
                                            modelName)
            domhelpers.superAppendAttribute(newNode, '_submodel_prefix',
                                            str(key))
            parentNode.appendChild(newNode)

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
            domhelpers.superAppendAttribute(newNode, '_submodel_prefix',
                                            self.submodel)
            domhelpers.superAppendAttribute(newNode, '_submodel_prefix',
                                            str(itemNum + self.start))
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

