# -*- test-case-name: twisted.test.test_woven -*-
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
import warnings
from twisted.web.microdom import parseString
from twisted.web import domhelpers


#sibling imports
import model
import template
import view
import utils

from twisted.python import components, failure
from twisted.python import log
from twisted.internet import defer

viewFactory = view.viewFactory
document = parseString("<xml />")

"""
DOMWidgets are views which can be composed into bigger views.
"""

DEBUG = 0

_RAISE = 1

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


    tagName = None
    def __init__(self, model = None, submodel = None, setup = None):
        self.errorFactory = Error
        self.become = None
        self._reset()
        view.View.__init__(self, model)
        self.node = None
        self.templateNode = None
        if submodel:
            self.submodel = submodel
        else:
            self.submodel = ""
        if setup:
            self.setupMethods = [setup]
        else:
            self.setupMethods = []
        self.initialize()

    def _reset(self):
        self.attributes = {}
        self.slots = {}
        self._children = []
    
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

        The return value of this may be a Deferred; if it is, then
        L{setData} will be called once the result is available.
        """
        return self.model.getData()
#         currentModel = self._getMyModel()
#         print "widget.getData currentModel submodel", currentModel, self.submodel
#         if currentModel is None:
#             return None
#         if hasattr(currentModel, 'getData'):
#             return currentModel.getData()
#         # Must have been set to a simple type, or a Deferred...
#         return currentModel

    def setData(self, data):
        """
        If the return value of L{getData} is a Deferred, I am called
        when the result of the Deferred is available.
        """
#         currentModel = self._getMyModel()
#         if currentModel is None:
#             raise NotImplementedError, "Can't set the data when there's no model to set it on."
        self.model.setData(data)

    def add(self, item):
        """
        Add `item' to the children of the resultant DOM Node of this widget.
        
        @type item: A DOM node or L{Widget}.
        """
        self._children.append(item)
        
    def insert(self, index, item):
        """
        Insert `item' at `index' in the children list of the resultant DOM Node
        of this widget.
        
        @type item: A DOM node or L{Widget}.
        """
        self._children.insert(index, item)

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
        return self._regenerate(request, node, data)
    
    def _regenerate(self, request, node, data):
        self._reset()
        self.setUp(request, node, data)
        for setupMethod in self.setupMethods:
            setupMethod(request, self, data)
        # generateDOM should always get a reference to the
        # templateNode from the original HTML
        result = self.generateDOM(request, self.templateNode or node)
        return result
    
    def setDataCallback(self, result, request, node):
        if isinstance(self.getData(), defer.Deferred):
            self.setData(result)
        data = self.getData()
        if isinstance(data, defer.Deferred):
            import warnings
            warnings.warn("%r has returned a Deferred multiple times for the "
                          "same request; this is a potential infinite loop."
                          % self.getData)
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
        if self.become:
            print "becoming"
            become = self.become
            self.become = None
            parent = node.parentNode
            node.parentNode = None
            old = node.cloneNode(1)
            node.parentNode = parent
            gen = become.generateDOM(request, node)
            del old.attributes['model']
            gen.appendChild(self.cleanNode(old))
            self.node = gen
            return gen
        if DEBUG:
            template = node.toxml()
            log.msg(template)
        if not self.tagName:
            self.tagName = self.templateNode.tagName
        if node is not self.templateNode:
            parent = node.parentNode
            node = document.createElement(self.tagName)
            node.parentNode = parent
        else:
            parentNode = node.parentNode
            node.parentNode = None
            new = node.cloneNode(1)
            node.parentNode = parentNode
            node = self.cleanNode(new)
        #print "NICE CLEAN NODE", node.toxml(), self._children
        for key, value in self.attributes.items():
            node.setAttribute(key, value)
        for item in self._children:
            if hasattr(item, 'generateDOM'):
                item = item.generateDOM(request, node)
            node.appendChild(item)
        #print "WE GOT A NODE", node.toxml()
        self.node = node
        return self.node

    def modelChanged(self, payload):
        request = payload['request']
        oldNode = self.node
        if payload.has_key(self.submodel):
            data = payload[self.submodel]
        else:
            data = self.getData()
        newNode = self._regenerate(request, oldNode, data)
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
        print "setError called", self
        self.become = self.errorFactory(self.model, message)
#        self.modelChanged({'request': request})

    def getPattern(self, name, default = None):
        """Get a named slot from the incoming template node. Returns a copy
        of the node and all it's children. If there was more than one node with
        the same slot identifier, they will be returned in a round-robin fashion.
        """
        #print self.templateNode.toxml()
        if self.slots.has_key(name):
            slots = self.slots[name]
        else:
            sm = self.submodel.split('/')[-1]
            slots = domhelpers.locateNodes(self.templateNode, name + 'Of', sm)
            if not slots:
                node = domhelpers.getIfExists(self.templateNode, name)
                if not node:
                    msg = 'WARNING: No template nodes were found '\
                              '(tagged %s="%s"'\
                              ' or slot="%s") for node %s' % (name + "Of", 
                                            sm, name, self.templateNode)
                    if default is _RAISE:
                        raise Exception(msg)
                    warnings.warn(msg)
                    return default
                slots = [node]
            self.slots[name] = slots
        slot = slots.pop(0)
        slots.append(slot)
        parentNode = slot.parentNode
        slot.parentNode = None
        clone = slot.cloneNode(1)
        slot.parentNode = parentNode
        return clone

wvfactory_Widget = viewFactory(Widget)


class WidgetNodeMutator(template.NodeMutator):
    """A WidgetNodeMutator replaces the node that is passed into generate
    with the result of generating the Widget it adapts.
    """
    def generate(self, request, node):
        newNode = self.data.generate(request, node)
        if isinstance(newNode, defer.Deferred):
            return newNode
        nodeMutator = template.NodeNodeMutator(newNode)
        nodeMutator.d = self.d
        return nodeMutator.generate(request, node)

components.registerAdapter(WidgetNodeMutator, Widget, template.INodeMutator)


class DefaultWidget(Widget):
    def generate(self, request, node):
        """
        By default, we just return the node unchanged
        """
        if self.become:
            become = self.become
            self.become = None
            parent = node.parentNode
            node.parentNode = None
            old = node.cloneNode(1)
            node.parentNode = parent
            gen = become.generateDOM(request, node)
            del old.attributes['model']
            gen.appendChild(self.cleanNode(old))
            return gen
        return node

wvfactory_DefaultWidget = viewFactory(DefaultWidget)
wvfactory_None = viewFactory(DefaultWidget)


class Text(Widget):
    """
    A simple Widget that renders some text.
    """
    def __init__(self, text, raw=0, clear=1):
        """
        @param text: The text to render.
        @type text: A string or L{model.Model}.
        @param raw: A boolean that specifies whether to render the text as
              a L{domhelpers.RawText} or as a DOM TextNode.
        """
        self.raw = raw
        self.clear = clear
        if isinstance(text, model.Model):
            Widget.__init__(self, text)
        else:
            Widget.__init__(self, model.Model())
        self.text = text
    
    def generateDOM(self, request, node):
        if node and self.clear:
            domhelpers.clearNode(node)
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

wvfactory_Text = viewFactory(Text)


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

wvfactory_Image = viewFactory(Image)


class Error(Widget):
    tagName = 'span'
    def __init__(self, model, message=""):
        Widget.__init__(self, model)
        self.message = message
    
    def generateDOM(self, request, node):
        self['style'] = 'color: red'
        self.add(Text(" " + self.message))
        return Widget.generateDOM(self, request, node)

wvfactory_Error = viewFactory(Error)


class Div(Widget):
    tagName = 'div'

wvfactory_Div = viewFactory(Div)


class Span(Widget):
    tagName = 'span'

wvfactory_Span = viewFactory(Span)


class Br(Widget):
    tagName = 'br'

wvfactory_Br = viewFactory(Br)


class Input(Widget):
    tagName = 'input'    
    def setSubmodel(self, submodel):
        self.submodel = submodel
        self['name'] = submodel

    def generateDOM(self, request, node):
        mVal = self.getData()
        if not self.attributes.has_key('value'):
            self['value'] = str(mVal)
        return Widget.generateDOM(self, request, node)

wvfactory_Input = viewFactory(Input)


class CheckBox(Input):
    def initialize(self):
        self['type'] = 'checkbox'

wvfactory_CheckBox = viewFactory(CheckBox)


class RadioButton(Input):
    def initialize(self):
        self['type'] = 'radio'

wvfactory_RadioButton = viewFactory(RadioButton)


class File(Input):
    def initialize(self):
        self['type'] = 'file'

wvfactory_File = viewFactory(File)


class Hidden(Input):
    def initialize(self):
        self['type'] = 'hidden'

wvfactory_Hidden = viewFactory(Hidden)


class InputText(Input):
    def initialize(self):
        self['type'] = 'text'

wvfactory_InputText = viewFactory(InputText)


class PasswordText(Input):
    """
    I render a password input field.
    """
    def initialize(self):
        self['type'] = 'password'

wvfactory_PasswordText = viewFactory(PasswordText)


class Button(Input):
    def initialize(self):
        self['type'] = 'button'

wvfactory_Button = viewFactory(Button)


class Select(Input):
    tagName = 'select'

wvfactory_Select = viewFactory(Select)


class Option(Input):
    tagName = 'option'
    def initialize(self):
        self.text = ''

    def setText(self, text):
        """
        Set the text to be displayed within the select menu.
        """
        self.text = text

    def setValue(self, value):
        self['value'] = str(value)

    def generateDOM(self, request, node):
        self.add(Text(self.text or self.getData()))
        return Input.generateDOM(self, request, node)

wvfactory_Option = viewFactory(Option)


class Anchor(Widget):
    tagName = 'a'
    trailingSlash = ''
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
        self['href'] = href or str(data) + self.trailingSlash
        if data is None:
            data = ""
        self.add(Text(self.text or data, self.raw, 0))
        return Widget.generateDOM(self, request, node)

wvfactory_Anchor = viewFactory(Anchor)


class DirectoryAnchor(Anchor):
    trailingSlash = '/'

wvfactory_DirectoryAnchor = viewFactory(DirectoryAnchor)


def appendModel(newNode, modelName):
    if newNode is None: return
    curModel = newNode.getAttribute('model')
    if curModel is None:
        newModel = str(modelName)
    else:
        newModel = curModel + '/' + str(modelName)
    newNode.setAttribute('model', newModel)


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
        listHeader = self.getPattern('listHeader', None)
        listFooter = self.getPattern('listFooter', None)
        emptyList = self.getPattern('emptyList', None)
        domhelpers.clearNode(node)
        if not listHeader is None:
            node.appendChild(listHeader)
        data = self.getData()
        if self._has_data(data):
            self._iterateData(node, self.submodel, data)
        elif not emptyList is None:
            node.appendChild(emptyList)
        if not listFooter is None:
            node.appendChild(listFooter)
        return node

    def _has_data(self, data):
        try:
            return len(data)
        except (TypeError, AttributeError):
            return 0

    def _iterateData(self, parentNode, submodel, data):
        currentListItem = 0
        for itemNum in range(len(data)):
            # theory: by appending copies of the li node
            # each node will be handled once we exit from
            # here because handleNode will then recurse into
            # the newly appended nodes

            newNode = self.getPattern('listItem', default = None)
            if not newNode:
                newNode = self.getPattern('item', default = _RAISE)
                if newNode:
                    warnings.warn("itemOf= is deprecated, "
                                        "please use listItemOf instead",
                                        DeprecationWarning)

            appendModel(newNode, itemNum)
            if not newNode.getAttribute("view"):
                newNode.setAttribute("view", "DefaultWidget")
            parentNode.appendChild(newNode)

wvfactory_List = viewFactory(List)


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

    def _iterateData(self, parentNode, submodel, data):
        """
        """
        currentListItem = 0
        for key in data.keys():
            newNode = self.getPattern('keyedListItem')
            if not newNode:
                newNode = self.getPattern('item', _RAISE)
                if newNode:
                    warnings.warn("itemOf= is deprecated, "
                                        "please use listItemOf instead",
                                        DeprecationWarning)
            
            appendModel(newNode, key)
            if not newNode.getAttribute("view"):
                newNode.setAttribute("view", "DefaultWidget")
            parentNode.appendChild(newNode)

wvfactory_KeyedList = viewFactory(KeyedList)


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
        domhelpers.clearNode(node)
        
        if self.end:
            listSize = self.end - self.start
            if listSize > len(self.getData()):
                listSize = len(self.getData())
        else:
            listSize = len(self.getData())
        for itemNum in range(listSize):
            if itemNum % self.columns == 0:
                row = self.getPattern('listRow')
                domhelpers.clearNode(row)
                node.appendChild(row)

            newNode = self.getPattern('columnListItem')
            if not newNode:
                newNode = self.getPattern('item', _RAISE)
                if newNode:
                    warnings.warn("itemOf= is deprecated, "
                                        "please use listItemOf instead",
                                        DeprecationWarning)

            appendModel(newNode, itemNum + self.start)
            if not newNode.getAttribute("view"):
                newNode.setAttribute("view", "DefaultWidget")
            row.appendChild(newNode)
        return node

wvfactory_ColumnList = viewFactory(ColumnList)


class Bold(Widget):
    tagName = 'b'

wvfactory_Bold = viewFactory(Bold)


class Table(Widget):
    tagName = 'table'

wvfactory_Table = viewFactory(Table)


class Row(Widget):
    tagName = 'tr'

wvfactory_Row = viewFactory(Row)


class Cell(Widget):
    tagName = 'td'

wvfactory_Cell = viewFactory(Cell)


class RawText(Widget):
    def generateDOM(self, request, node):
        self.node = domhelpers.RawText(self.getData())
        return self.node

wvfactory_RawText = viewFactory(RawText)

def getSubview(request, node, model, viewName):
    """Get a sub-view from me.
    """
    if viewName == "None":
        return DefaultWidget(model)
    view = None
    self = globals()

    vm = self.get(viewName, None)
    if vm:
        view = vm(model)

    return view


view.registerViewForModel(Text, model.StringModel)
view.registerViewForModel(List, model.ListModel)
view.registerViewForModel(KeyedList, model.DictionaryModel)
