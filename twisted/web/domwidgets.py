# DOMWidgets

from xml.dom.minidom import parseString
from twisted.python.mvc import View, Model
from twisted.python import domhelpers

document = parseString("<xml />")

"""
DOMWidgets are views which can be composed into bigger views.
"""

class Widget(View):
    tagName = 'span'
    def __init__(self, model):
        self.attributes = {}
        View.__init__(self, model)
        self.become = None
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
        # This is safe because id is only specified in the TEMPLATE, never
        # in the request submitted by the user.
        # if a hacker hacks your templates, they could make this do bad
        # stuff possibly. So secure your filesystem.
        # of course by the time they hack your filesystem they could just
        # edit the python source to do anything they want.
        
        # we should at least check for and prevent the use of a semicolon
        id = self.id
        if self.node:
            nodexml = self.node.toxml()
        assert id is not None, 'The model attribute was not set on the node; e.g. &lt;div model="foo" view="Text"&gt; would apply the Text widget to model.foo.'
        assert ';' not in id, "Semicolon is not legal in widget ids."
        try:
            return eval ("self.model." + id)
        except:
            return ""

    def add(self, item):
        self.children.append(item)

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
            node.appendChild(document.createTextNode(str(self.getData())))
            return node
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

class Anchor(Widget):
    tagName = 'a'
    def setText(self, text):
        self.text = text
    
    def setLink(self, href):
        self['href'] = href
    
    def setAttributes(self, request):
        self['href'] = self.getData()
        
    def generateDOM(self, request, node):
        self.setAttributes(request)
        node = Widget.generateDOM(self, request, node)
        node.appendChild(document.createTextNode(self.getData()))
        return node

class GetAnchor(Anchor):
    def setAttributes(self, request):
        self['href'] = "?%s=%s" % (self.id, self.getData())

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
            
            domhelpers.superPrependAttribute(newNode, 'model', self.id + '[' + str(itemNum) + ']')
            node.appendChild(newNode)
        return node
