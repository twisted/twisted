# DOMWidgets

from xml.dom.minidom import parseString
from twisted.python.mvc import View, Model
from twisted.web import domhelpers

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
        self.id=""
        self.initialize()

    def setId(self, id):
        """
        I use the ID to know which attribute in self.model I am responsible for
        """
        self.id = id

    def getData(self):
        """
        I have a model; however since I am a widget I am only responsible
        for a portion of that model. This method returns the portion I am
        responsible for.
        """
        # this should be spelled
        # eval ("self.model" + "." + self.id)
        #return getattr(self.model, self.id)

        # This is safe because id is only specified in the TEMPLATE, never
        # in the request submitted by the user.
        # if a hacker hacks your templates, they could make this do bad
        # stuff possibly. So secure your filesystem.
        # of course by the time they hack your filesystem they could just
        # edit the python source to do anything they want.
        
        # we should at least check for and prevent the use of a semicolon
        assert ';' not in self.id, "Semicolon is not legal in widget ids."
        return eval ("self.model." + self.id)

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
        try:
            node.removeAttribute('model')
        except KeyError: pass
        try:
            node.removeAttribute('controller')
        except KeyError: pass
        try:
            node.removeAttribute('view')
        except KeyError: pass
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
        if isinstance(text, Model):
            Widget.__init__(self, text)
        else:
            Widget.__init__(self, Model())
        self.text = text
    
    def render(self, request):
        if isinstance(self.text, Model):
            self.node.appendChild(document.createTextNode(str(self.getData())))
            return self.node
        else:            
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
        mVal = self.getData()
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

class List(Widget):
    """
    I am a widget which knows how to render a python list.
    
    A List should be specified in the template HTML as so:
    
    <ul id="blah" view="List">
        <li id="listItem" view="Text">Foo</li>
    </ul>
    """
    tagName = 'ul'
    def render(self, request):
        node = Widget.render(self, request)
        # xxx with this implementation all elements of the list must use the same view widget
        listItem = domhelpers.get(node, 'listItem').cloneNode(1)
        domhelpers.clearNode(node)
        for itemNum in range(len(self.getData())):
            # theory: by appending copies of the li node
            # each node will be handled once we exit from
            # here because handleNode will then recurse into
            # the newly appended nodes
            
            # Issue; how to spell each subnode's id?
            # This is the real question that needs to be solved.
            newNode = listItem.cloneNode(1)
            domhelpers.superSetAttribute(newNode, 'model', self.id + '[' + str(itemNum) + ']')
            node.appendChild(newNode)
        return node
