# DOMWidgets

import urllib
from xml.dom.minidom import parseString

from twisted.python.mvc import View, Model
from twisted.python import domhelpers

document = parseString("<xml />")

"""
DOMWidgets are views which can be composed into bigger views.
"""

class Widget(View):
    """A Widget wraps an object, its model, for display. The model can be a
    simple Python object (string, list, etc.) or it can be an instance of MVC.Model.
    (The former case is for interface purposes, so that the rest of the code does
    not have to treat simple objects differently from Model instances.)
    If the model is a Model, there are two possibilities:
        we are being called to enable an operation on the model
        we are really being called to enable an operation on an attribute of the
        model, which we will call the submodel
    """
    tagName = None
    def __init__(self, model, submodel = None):
        self.attributes = {}
        View.__init__(self, model)
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
        print "setId is deprecated; please use setSubmodel."
        self.submodel = id

    def setSubmodel(self, submodel):
        """
        I use the submodel to know which attribute in self.model I am responsible for
        """
        self.submodel = submodel

    def getData(self):
        """
        I have a model; however since I am a widget I am only responsible
        for a portion of that model. This method returns the portion I am
        responsible for.
        """
        if not isinstance(self.model, Model): # see __class__.doc
            return self.model

        assert self.submodel is not None, 'The model attribute was not set on the node; e.g. &lt;div model="foo" view="Text"&gt; would apply the Text widget to model.foo.'
        assert ';' not in self.submodel, "Semicolon is not legal in widget ids."
        
        # This call to eval is safe because id is only specified in the TEMPLATE, never
        # in the request submitted by the user.
        # if a hacker hacks your templates, they could make this do bad
        # stuff possibly. So secure your filesystem.
        # of course by the time they hack your filesystem they could just
        # edit the python source to do anything they want.        
        try:
            return eval ("self.model." + self.submodel)
        except:
            return ""

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

    def generateDOM(self, request, node):
        if self.tagName and str(node.tagName) != self.tagName:
            node = document.createElement(self.tagName)
        else:
            node = self.cleanNode(node)
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

    def setError(self, message):
        self.become = Error(self.model, message)

    def initialize(self):
        pass

class Text(Widget):
    def __init__(self, text):
        if isinstance(text, Model):
            Widget.__init__(self, text)
        else:
            Widget.__init__(self, Model())
        self.text = text
    
    def generateDOM(self, request, node):
        if isinstance(self.text, Model):
            textNode = document.createTextNode(str(self.getData()))
            if node is None:
                return textNode
            node.appendChild(textNode)
            return node
        else:            
            return document.createTextNode(self.text)


class Image(Text):
    tagName = 'img'
    def generateDOM(self, request, node):
        if isinstance(self.text, Model):
            data = self.getData()
        else:
            data = self.text
        node = Widget.generateDOM(self, request, node)
        node.setAttribute('src', data)
        return node


class Error(Widget):
    tagName = 'div'
    def __init__(self, model, message=""):
        Widget.__init__(self, model)
        self['style'] = 'color: red'
        self.add(Text(message))
    
    def add(self, item):
        item.error = None
        self.children.append(item)


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
            self['value'] = mVal
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

class Button(Input):
    def initialize(self):
        self['type'] = 'button'

class Select(Input):
    tagName = 'select'

class Option(Input):
    tagName = 'option'

class Anchor(Widget):
    tagName = 'a'
    def initialize(self):
        self.baseHREF = ""
        self.parameters = {}
    
    def setLink(self, href):
        self.baseHREF= href
    
    def setParameter(self, key, value):
        self.parameters[key] = value

    def generateDOM(self, request, node):
        href = self.baseHREF
        params = urllib.urlencode(self.parameters)
        if params:
            href = href + '?' + params
        self['href'] = href
        node = Widget.generateDOM(self, request, node)
        node.appendChild(document.createTextNode(self.getData()))
        return node

class List(Widget):
    """
    I am a widget which knows how to generateDOM for a python list.
    
    A List should be specified in the template HTML as so:
    
    <ul id="blah" view="List">
        <li id="listItem" view="Text">Foo</li>
    </ul>
    
    Where blah is the name of a list on the model; eg self.model.blah = ['foo', 'bar']
    """
    tagName = None
    def generateDOM(self, request, node):
        node = Widget.generateDOM(self, request, node)
        # xxx with this implementation all elements of the list must use the same view widget
        listItem = domhelpers.get(node, 'listItem')
        domhelpers.clearNode(node)
        for itemNum in range(len(self.getData())):
            # theory: by appending copies of the li node
            # each node will be handled once we exit from
            # here because handleNode will then recurse into
            # the newly appended nodes
            
            newNode = listItem.cloneNode(1)
            
            domhelpers.superPrependAttribute(newNode, 'model', self.submodel + '[' + str(itemNum) + ']')
            node.appendChild(newNode)
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
        else:
            listSize = len(self.getData())
        for itemNum in range(listSize):
            if itemNum % self.columns == 0:
                row = listRow.cloneNode(1)
                node.appendChild(row)
            newNode = listItem.cloneNode(1)
            domhelpers.superPrependAttribute(newNode, 'model', self.submodel + '[' + str(itemNum + self.start) + ']')
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