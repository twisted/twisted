# DOMWidgets

from xml.dom.minidom import parseString
from twisted.python.mvc import View

document = parseString("<xml />")

"""
DOMWidgets are views which can be composed into bigger views.
"""

class Widget(View):
    tagName = 'span'
    def __init__(self, model):
        self.attributes = {}
        View.__init__(self, model)
        self.error = None
        self.children = []
        self.node = None
        self.initialize()

    def add(self, item):
        self.children.append(item)

    def setNode(self, node):
        """
        Set a node for this widget to use instead of creating one programatically.
        Useful for looking up a node in a template and using that.
        """
        self.node = node

    def cloneNode(self):
        node = self.node.cloneNode(1)
        # Do your part:
        # Prevent infinite recursion
        node.removeAttribute('id')
        node.removeAttribute('controller')
        node.removeAttribute('view')
        return node

    def render(self, request):
        if self.node is None:
            node = document.createElement(self.tagName)
        else:
            node = self.cloneNode()
        for key, value in self.attributes.items():
            node.setAttribute(key, value)
        for item in self.children:
            if hasattr(item, 'render'):
                item = item.render(request)
            node.appendChild(item)
        if self.error is None:
            return node
        err = Error(self.model, message = self.error)
        err.add(self)
        return err.render(request)

    def __setitem__(self, item, value):
        self.attributes[item] = value
    
    def __getitem__(self, item):
        return self.attributes[item]

    def setError(self, message):
        self.error = message

    def initialize(self):
        pass

class Text(Widget):
    def __init__(self, text):
        self.text = text
    
    def render(self, request):
        return document.createTextNode(self.text)

class Error(Widget):
    def __init__(self, model, message=""):
        Widget.__init__(self, model)
        self['style'] = 'color: red'
        self.add(Text(message))
    
    def add(self, item):
        item.error = None
        self.children.append(item)

class Div(Widget):
    tagName = 'div'

class Input(Widget):
    tagName = 'input'    
    def setId(self, id):
        self.id=id
        self['name'] = id

    def render(self, request):
        mVal = getattr(self.model, self.id, None)
        if mVal:
            self['value'] = mVal
        return Widget.render(self, request)

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

class Anchor(Widget):
    tagName = 'a'
    def setText(self, text):
        self.text = text
    
    def setLink(self, href):
        self['href'] = href
    
    def render(self, request):
        node = Widget.render(self, request)
        node.appendChild(d.createTextNode(self.text))
        return node