# -*- test-case-name: twisted.web.test.test_woven -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


# DOMWidgets

from __future__ import nested_scopes

import urllib
import warnings
from twisted.web.microdom import parseString, Element, Node
from twisted.web import domhelpers


#sibling imports
import model
import template
import view
import utils
import interfaces

from twisted.python import components, failure
from twisted.python import reflect
from twisted.python import log
from twisted.internet import defer

viewFactory = view.viewFactory
document = parseString("<xml />", caseInsensitive=0, preserveCase=0)

missingPattern = Element("div", caseInsensitive=0, preserveCase=0)
missingPattern.setAttribute("style", "border: dashed red 1px; margin: 4px")

"""
DOMWidgets are views which can be composed into bigger views.
"""

DEBUG = 0

_RAISE = 1

class Dummy:
    pass

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
          its model.
    @ivar model: If the current model is an L{model.Model}, then the result of
          model.getData(). Otherwise the original object itself.
    """
    # wvupdate_xxx method signature: request, widget, data; returns None

    # Don't do lots of work setting up my stacks; they will be passed to me
    setupStacks = 0
    
    # Should we clear the node before we render the widget?
    clearNode = 0
    
    # If some code has to ask if a widget is livePage, the answer is yes
    livePage = 1
    
    tagName = None
    def __init__(self, model = None, submodel = None, setup = None, controller = None, viewStack=None, *args, **kwargs):
        """
        @type model: L{interfaces.IModel}

        @param submodel: see L{Widget.setSubmodel}
        @type submodel: String

        @type setup: Callable
        """
        self.errorFactory = Error
        self.controller = controller
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
        self.viewStack = viewStack
        self.initialize(*args, **kwargs)

    def _reset(self):
        self.attributes = {}
        self.slots = {}
        self._children = []

    def initialize(self, *args, **kwargs):
        """
        Use this method instead of __init__ to initialize your Widget, so you
        don't have to deal with calling the __init__ of the superclass.
        """
        pass

    def setSubmodel(self, submodel):
        """
        I use the submodel to know which attribute in self.model I am responsible for
        """
        self.submodel = submodel

    def getData(self, request=None):
        """
        I have a model; however since I am a widget I am only responsible
        for a portion of that model. This method returns the portion I am
        responsible for.

        The return value of this may be a Deferred; if it is, then
        L{setData} will be called once the result is available.
        """
        return self.model.getData(request)

    def setData(self, request=None, data=None):
        """
        If the return value of L{getData} is a Deferred, I am called
        when the result of the Deferred is available.
        """
        self.model.setData(request, data)

    def add(self, item):
        """
        Add `item' to the children of the resultant DOM Node of this widget.

        @type item: A DOM node or L{Widget}.
        """
        self._children.append(item)

    def appendChild(self, item):
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
        if not DEBUG:
            if node.attributes.has_key('model'):
                del node.attributes['model']
            if node.attributes.has_key('view'):
                del node.attributes['view']
            if node.attributes.has_key('controller'):
                del node.attributes['controller']
        return node

    def generate(self, request, node):
        data = self.getData(request)
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
        if DEBUG:
            result.attributes['woven_class'] = reflect.qual(self.__class__)
        return result

    def setDataCallback(self, result, request, node):
        if isinstance(self.getData(request), defer.Deferred):
            self.setData(request, result)
        data = self.getData(request)
        if isinstance(data, defer.Deferred):
            import warnings
            warnings.warn("%r has returned a Deferred multiple times for the "
                          "same request; this is a potential infinite loop."
                          % self.getData)
            data.addCallback(self.setDataCallback, request, node)
            data.addErrback(utils.renderFailure, request)
            return data

        newNode = self._regenerate(request, node, result)
        returnNode = self.dispatchResult(request, node, newNode)
        # isinstance(Element) added because I was having problems with
        # this code trying to call setAttribute on my RawTexts -radix 2003-5-28
        if hasattr(self, 'outgoingId') and isinstance(returnNode, Element):
            returnNode.attributes['id'] = self.outgoingId
        self.handleNewNode(request, returnNode)
        self.handleOutstanding(request)
        if self.subviews:
            self.getTopModel().subviews.update(self.subviews)
        self.controller.domChanged(request, self, returnNode)

        ## We need to return the result along the callback chain
        ## so that any other views which added a setDataCallback
        ## to the same deferred will get the correct data.
        return result

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
            #print "becoming"
            become = self.become
            self.become = None
            parent = node.parentNode
            node.parentNode = None
            old = node.cloneNode(1)
            node.parentNode = parent
            gen = become.generateDOM(request, node)
            if old.attributes.has_key('model'):
                del old.attributes['model']
            del old.attributes['controller']
            gen.appendChild(old)
            self.node = gen
            return gen
        if DEBUG:
            template = node.toxml()
            log.msg(template)
        if not self.tagName:
            self.tagName = self.templateNode.tagName
        if node is not self.templateNode or self.tagName != self.templateNode.tagName:
            parent = node.parentNode
            node = document.createElement(self.tagName, caseInsensitive=0, preserveCase=0)
            node.parentNode = parent
        else:
            parentNode = node.parentNode
            node.parentNode = None
            if self.clearNode:
                new = node.cloneNode(0)
            else:
                new = node.cloneNode(1)
            node.parentNode = parentNode
            node = self.cleanNode(new)
        #print "NICE CLEAN NODE", node.toxml(), self._children
        node.attributes.update(self.attributes)
        for item in self._children:
            if hasattr(item, 'generate'):
                parentNode = node.parentNode
                node.parentNode = None
                item = item.generate(request, node.cloneNode(1))
                node.parentNode = parentNode
            node.appendChild(item)
        #print "WE GOT A NODE", node.toxml()
        self.node = node
        return self.node

    def modelChanged(self, payload):
        request = payload.get('request', None)
        if request is None:
            request = Dummy()
            request.d = document
        oldNode = self.node
        if payload.has_key(self.submodel):
            data = payload[self.submodel]
        else:
            data = self.getData(request)
        newNode = self._regenerate(request, oldNode, data)
        returnNode = self.dispatchResult(request, oldNode, newNode)
        # shot in the dark: this seems to make *my* code work.  probably will
        # break if returnNode returns a Deferred, as it's supposed to be able
        # to do -glyph
#        self.viewStack.push(self)
#        self.controller.controllerStack.push(self.controller)
        self.handleNewNode(request, returnNode)
        self.handleOutstanding(request)
        self.controller.domChanged(request, self, returnNode)

    def __setitem__(self, item, value):
        """
        Convenience syntax for adding attributes to the resultant DOM Node of
        this widget.
        """
        assert value is not None
        self.attributes[item] = value

    setAttribute = __setitem__

    def __getitem__(self, item):
        """
        Convenience syntax for getting an attribute from the resultant DOM Node
        of this widget.
        """
        return self.attributes[item]

    getAttribute = __getitem__

    def setError(self, request, message):
        """
        Convenience method for allowing a Controller to report an error to the
        user. When this is called, a Widget of class self.errorFactory is instanciated
        and set to self.become. When generate is subsequently called, self.become
        will be responsible for mutating the DOM instead of this widget.
        """
        #print "setError called", self
        id = self.attributes.get('id', '')
        
        self.become = self.errorFactory(self.model, message)
        self.become['id'] = id
#        self.modelChanged({'request': request})

    def getTopModel(self):
        """Get a reference to this page's top model object.
        """
        top = self.model
        while top.parent is not None:
            top = top.parent
        return top

    def getAllPatterns(self, name, default=missingPattern, clone=1, deep=1):
        """Get all nodes below this one which have a matching pattern attribute.
        """
        if self.slots.has_key(name):
            slots = self.slots[name]
        else:
            sm = self.submodel.split('/')[-1]
            slots = domhelpers.locateNodes(self.templateNode, name + 'Of', sm)
            if not slots:
#                slots = domhelpers.locateNodes(self.templateNode, "pattern", name, noNesting=1)
                matcher = lambda n, name=name: isinstance(n, Element) and \
                            n.attributes.has_key("pattern") and n.attributes["pattern"] == name
                recurseMatcher = lambda n: isinstance(n, Element) and not n.attributes.has_key("view") and not n.attributes.has_key('model')
                slots = domhelpers.findNodesShallowOnMatch(self.templateNode, matcher, recurseMatcher)
                if not slots:
                    msg = 'WARNING: No template nodes were found '\
                              '(tagged %s="%s"'\
                              ' or pattern="%s") for node %s (full submodel path %s)' % (name + "Of",
                                            sm, name, self.templateNode, `self.submodel`)
                    if default is _RAISE:
                        raise Exception(msg)
                    if DEBUG:
                        warnings.warn(msg)
                    if default is missingPattern:
                        newNode = missingPattern.cloneNode(1)
                        newNode.appendChild(document.createTextNode(msg))
                        return [newNode]
                    if default is None:
                        return None
                    return [default]
            self.slots[name] = slots
        if clone:
            return [x.cloneNode(deep) for x in slots]
        return slots

    def getPattern(self, name, default=missingPattern, clone=1, deep=1):
        """Get a named slot from the incoming template node. Returns a copy
        of the node and all its children. If there was more than one node with
        the same slot identifier, they will be returned in a round-robin fashion.
        """
        slots = self.getAllPatterns(name, default=default, clone=0)
        if slots is None:
            return None
        slot = slots.pop(0)
        slots.append(slot)
        if clone:
            parentNode = slot.parentNode
            slot.parentNode = None
            clone = slot.cloneNode(deep)
            if clone.attributes.has_key('pattern'):
                del clone.attributes['pattern']
            elif clone.attributes.has_key(name + 'Of'):
                del clone.attributes[name + 'Of']
            slot.parentNode = parentNode
            if DEBUG:
                clone.attributes['ofPattern'] = name + 'Of'
                clone.attributes['nameOf'] = self.submodel.split('/')[-1]
            return clone
        if DEBUG:
            slot.attributes['ofPattern'] = name + 'Of'
            slot.attributes['nameOf'] = self.submodel.split('/')[-1]
        return slot

    def addUpdateMethod(self, updateMethod):
        """Add a method to this widget that will be called when the widget
        is being rendered. The signature for this method should be
        updateMethod(request, widget, data) where widget will be the
        instance you are calling addUpdateMethod on.
        """
        self.setupMethods.append(updateMethod)

    def addEventHandler(self, eventName, handler, *args):
        """Add an event handler to this widget. eventName is a string
        indicating which javascript event handler should cause this
        handler to fire. Handler is a callable that has the signature
        handler(request, widget, *args).
        """
        def handlerUpdateStep(request, widget, data):
            extraArgs = ''
            for x in args:
                extraArgs += " ,'" + x.replace("'", "\\'") + "'"
            widget[eventName] = "return woven_eventHandler('%s', this%s)" % (eventName, extraArgs)
            setattr(self, 'wevent_' + eventName, handler)
        self.addUpdateMethod(handlerUpdateStep)
        
    def onEvent(self, request, eventName, *args):
        """Dispatch a client-side event to an event handler that was
        registered using addEventHandler.
        """
        eventHandler = getattr(self, 'wevent_' + eventName, None)
        if eventHandler is None:
            raise NotImplementedError("A client side '%s' event occurred,"
                    " but there was no event handler registered on %s." % 
                    (eventName, self))
                
        eventHandler(request, self, *args)


class DefaultWidget(Widget):
    def generate(self, request, node):
        """
        By default, we just return the node unchanged
        """
        self.cleanNode(node)
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

    def modelChanged(self, payload):
        """We're not concerned if the model has changed.
        """
        pass


class Attributes(Widget):
    """Set attributes on a node.

    Assumes model is a dictionary of attributes.
    """

    def setUp(self, request, node, data):
        for k, v in data.items():
            self[k] = v


class Text(Widget):
    """
    A simple Widget that renders some text.
    """
    def __init__(self, model, raw=0, clear=1, *args, **kwargs):
        """
        @param model: The text to render.
        @type model: A string or L{model.Model}.
        @param raw: A boolean that specifies whether to render the text as
              a L{domhelpers.RawText} or as a DOM TextNode.
        """
        self.raw = raw
        self.clearNode = clear
        Widget.__init__(self, model, *args, **kwargs)

    def generate(self, request, node):
        if self.templateNode is None:
            if self.raw:
                return domhelpers.RawText(str(self.getData(request)))
            else:
                return document.createTextNode(str(self.getData(request)))
        return Widget.generate(self, request, node)

    def setUp(self, request, node, data):
        if self.raw:
            textNode = domhelpers.RawText(str(data))
        else:
            textNode = document.createTextNode(str(data))
        self.appendChild(textNode)


class ParagraphText(Widget):
    """
    Like a normal text widget, but it takes line breaks in the text and
    formats them as HTML paragraphs.
    """
    def setUp(self, request, node, data):
        nSplit = data.split('\n')
        for line in nSplit:
            if line.strip():
                para = request.d.createElement('p', caseInsensitive=0, preserveCase=0)
                para.appendChild(request.d.createTextNode(line))
                self.add(para)

class Image(Widget):
    """
    A simple Widget that creates an `img' tag.
    """
    tagName = 'img'
    border = '0'
    def setUp(self, request, node, data):
        self['border'] = self.border
        self['src'] = data


class Error(Widget):
    tagName = 'span'
    def __init__(self, model, message="", *args, **kwargs):
        Widget.__init__(self, model, *args, **kwargs)
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

    def setUp(self, request, node, data):
        if not self.attributes.has_key('name') and not node.attributes.get('name'):
            if self.submodel:
                id = self.submodel
            else:
                id = self.attributes.get('id', node.attributes.get('id'))
            self['name'] = id
        if data is None:
            data = ''
        if not self.attributes.has_key('value'):
            self['value'] = str(data)


class CheckBox(Input):
    def setUp(self, request, node, data):
        self['type'] = 'checkbox'
        Input.setUp(self, request, node, data)


class RadioButton(Input):
    def setUp(self, request, node, data):
        self['type'] = 'radio'
        Input.setUp(self, request, node, data)


class File(Input):
    def setUp(self, request, node, data):
        self['type'] = 'file'
        Input.setUp(self, request, node, data)


class Hidden(Input):
    def setUp(self, request, node, data):
        self['type'] = 'hidden'
        Input.setUp(self, request, node, data)


class InputText(Input):
    def setUp(self, request, node, data):
        self['type'] = 'text'
        Input.setUp(self, request, node, data)


class PasswordText(Input):
    """
    I render a password input field.
    """
    def setUp(self, request, node, data):
        self['type'] = 'password'
        Input.setUp(self, request, node, data)


class Button(Input):
    def setUp(self, request, node, data):
        self['type'] = 'button'
        Input.setUp(self, request, node, data)


class Select(Input):
    tagName = 'select'


class Option(Widget):
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

    def setUp(self, request, node, data):
        self.add(Text(self.text or data))
        if data is None:
            data = ''
        if not self.attributes.has_key('value'):
            self['value'] = str(data)

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

    def setUp(self, request, node, data):
        href = self.baseHREF
        params = urllib.urlencode(self.parameters)
        if params:
            href = href + '?' + params
        self['href'] = href or str(data) + self.trailingSlash
        if data is None:
            data = ""
        self.add(Text(self.text or data, self.raw, 0))


class SubAnchor(Anchor):
    def initialize(self):
        warnings.warn(
            "SubAnchor is deprecated, you might want either Anchor or DirectoryAnchor",
            DeprecationWarning)
        Anchor.initialize(self)



class DirectoryAnchor(Anchor):
    trailingSlash = '/'


def appendModel(newNode, modelName):
    if newNode is None: return
    curModel = newNode.attributes.get('model')
    if curModel is None:
        newModel = str(modelName)
    else:
        newModel = '/'.join((curModel, str(modelName)))
    newNode.attributes['model'] = newModel


class List(Widget):
    """
    I am a widget which knows how to generateDOM for a python list.

    A List should be specified in the template HTML as so::

       | <ul model="blah" view="List">
       |     <li pattern="emptyList">This will be displayed if the list
       |         is empty.</li>
       |     <li pattern="listItem" view="Text">Foo</li>
       | </ul>

    If you have nested lists, you may also do something like this::

       | <table model="blah" view="List">
       |     <tr pattern="listHeader"><th>A</th><th>B</th></tr>
       |     <tr pattern="emptyList"><td colspan='2'>***None***</td></tr>
       |     <tr pattern="listItem">
       |         <td><span view="Text" model="1" /></td>
       |         <td><span view="Text" model="2" /></td>
       |     </tr>
       |     <tr pattern="listFooter"><td colspan="2">All done!</td></tr>
       | </table>

    Where blah is the name of a list on the model; eg::

       | self.model.blah = ['foo', 'bar']

    """
    tagName = None
    defaultItemView = "DefaultWidget"
    def generateDOM(self, request, node):
        node = Widget.generateDOM(self, request, node)
        listHeaders = self.getAllPatterns('listHeader', None)
        listFooters = self.getAllPatterns('listFooter', None)
        emptyLists = self.getAllPatterns('emptyList', None)
        domhelpers.clearNode(node)
        if listHeaders:
            node.childNodes.extend(listHeaders)
            for n in listHeaders: n.parentNode = node
        data = self.getData(request)
        if data:
            self._iterateData(node, self.submodel, data)
        elif emptyLists:
            node.childNodes.extend(emptyLists)
            for n in emptyLists: n.parentNode = node
        if listFooters:
            node.childNodes.extend(listFooters)
            for n in listFooters: n.parentNode = node
        return node

    def _iterateData(self, parentNode, submodel, data):
        currentListItem = 0
        retVal = [None] * len(data)
        for itemNum in range(len(data)):
            # theory: by appending copies of the li node
            # each node will be handled once we exit from
            # here because handleNode will then recurse into
            # the newly appended nodes

            newNode = self.getPattern('listItem')
            if newNode.getAttribute('model') == '.':
                newNode.removeAttribute('model')
            elif not newNode.attributes.get("view"):
                newNode.attributes["view"] = self.defaultItemView
            appendModel(newNode, itemNum)
            retVal[itemNum] = newNode
            newNode.parentNode = parentNode
#            parentNode.appendChild(newNode)
        parentNode.childNodes.extend(retVal)


class KeyedList(List):
    """
    I am a widget which knows how to display the values stored within a
    Python dictionary..

    A KeyedList should be specified in the template HTML as so::

       | <ul model="blah" view="KeyedList">
       |     <li pattern="emptyList">This will be displayed if the list is
       |         empty.</li>
       |     <li pattern="keyedListItem" view="Text">Foo</li>
       | </ul>

    I can take advantage of C{listHeader}, C{listFooter} and C{emptyList}
    items just as a L{List} can.
    """
    def _iterateData(self, parentNode, submodel, data):
        """
        """
        currentListItem = 0
        keys = data.keys()
        # Keys may be a tuple, if this is not a true dictionary but a dictionary-like object
        if hasattr(keys, 'sort'):
            keys.sort()
        for key in keys:
            newNode = self.getPattern('keyedListItem')
            if not newNode:
                newNode = self.getPattern('item', _RAISE)
                if newNode:
                    warnings.warn("itemOf= is deprecated, "
                                        "please use listItemOf instead",
                                        DeprecationWarning)

            appendModel(newNode, key)
            if not newNode.attributes.get("view"):
                newNode.attributes["view"] = "DefaultWidget"
            parentNode.appendChild(newNode)


class ColumnList(Widget):
    def __init__(self, model, columns=1, start=0, end=0, *args, **kwargs):
        Widget.__init__(self, model, *args, **kwargs)
        self.columns = columns
        self.start = start
        self.end = end

    def setColumns(self, columns):
        self.columns = columns

    def setStart(self, start):
        self.start = start

    def setEnd(self, end):
        self.end = end

    def setUp(self, request, node, data):
        pattern = self.getPattern('columnListRow', clone=0)
        if self.end:
            listSize = self.end - self.start
            if listSize > len(data):
                listSize = len(data)
        else:
            listSize = len(data)
        for itemNum in range(listSize):
            if itemNum % self.columns == 0:
                row = self.getPattern('columnListRow')
                domhelpers.clearNode(row)
                node.appendChild(row)

            newNode = self.getPattern('columnListItem')

            appendModel(newNode, itemNum + self.start)
            if not newNode.attributes.get("view"):
                newNode.attributes["view"] = "DefaultWidget"
            row.appendChild(newNode)
        node.removeChild(pattern)
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
        self.node = domhelpers.RawText(self.getData(request))
        return self.node

from types import StringType

class Link(Widget):
    """A utility class for generating <a href='foo'>bar</a> tags.
    """
    tagName = 'a'
    def setUp(self, request, node, data):
        # TODO: we ought to support Deferreds here for both text and href!
        if isinstance(data, StringType):
            node.tagName = self.tagName
            node.attributes["href"] = data
        else:
            data = self.model
            txt = data.getSubmodel(request, "text").getData(request)
            if not isinstance(txt, Node):
                txt = document.createTextNode(txt)
            lnk = data.getSubmodel(request, "href").getData(request)
            self['href'] = lnk
            node.tagName = self.tagName
            domhelpers.clearNode(node)
            node.appendChild(txt)

class RootRelativeLink(Link):
    """
    Just like a regular Link, only it makes the href relative to the
    appRoot (that is, request.getRootURL()).
    """
    def setUp(self, request, node, data):
        # hack, hack: some juggling so I can type less and share more
        # code with Link
        st = isinstance(data, StringType)
        if st:
            data = request.getRootURL() + '/' + data
        Link.setUp(self, request, node, data)
        if not st:
            self['href'] = request.getRootURL() + '/' + self['href']

class ExpandMacro(Widget):
    """A Macro expansion widget modeled after the METAL expander
    in ZPT/TAL/METAL. Usage:
    
    In the Page that is being rendered, place the ExpandMacro widget
    on the node you want replaced with the Macro, and provide nodes
    tagged with fill-slot= attributes which will fill slots in the Macro::
    
        def wvfactory_myMacro(self, request, node, model):
            return ExpandMacro(
                model,
                macroFile="MyMacro.html",
                macroName="main")
        
        <div view="myMacro">
            <span fill-slot="greeting">Hello</span>
            <span fill-slot="greetee">World</span>
        </div>
    
    Then, in your Macro template file ("MyMacro.html" in the above
    example) designate a node as the macro node, and nodes
    inside that as the slot nodes::
    
        <div macro="main">
            <h3><span slot="greeting" />, <span slot="greetee" />!</h3>
        </div>
    """
    def __init__(self, model, macroTemplate = "", macroFile="", macroFileDirectory="", macroName="", **kwargs):
        self.macroTemplate = macroTemplate
        self.macroFile=macroFile
        self.macroFileDirectory=macroFileDirectory
        self.macroName=macroName
        Widget.__init__(self, model, **kwargs)

    def generate(self, request, node):
        if self.macroTemplate:
            templ = view.View(
                self.model,
                template = self.macroTemplate).lookupTemplate(request)
        else:
            templ = view.View(
                self.model,
                templateFile=self.macroFile,
                templateDirectory=self.macroFileDirectory).lookupTemplate(request)

        ## We are going to return the macro node from the metatemplate,
        ## after replacing any slot= nodes in it with fill-slot= nodes from `node'
        macrolist = domhelpers.locateNodes(templ.childNodes, "macro", self.macroName)
        assert len(macrolist) == 1, ("No macro or more than "
            "one macro named %s found." % self.macroName)

        macro = macrolist[0]
        del macro.attributes['macro']
        slots = domhelpers.findElementsWithAttributeShallow(macro, "slot")
        for slot in slots:
            slotName = slot.attributes.get("slot")
            fillerlist = domhelpers.locateNodes(node.childNodes, "fill-slot", slotName)
            assert len(fillerlist) <= 1, "More than one fill-slot found with name %s" % slotName
            if len(fillerlist):
                filler = fillerlist[0]
                filler.tagName = filler.endTagName = slot.tagName
                del filler.attributes['fill-slot']
                del slot.attributes['slot']
                filler.attributes.update(slot.attributes)
                slot.parentNode.replaceChild(filler, slot)

        return macro

class DeferredWidget(Widget):
    def setDataCallback(self, result, request, node):
        model = result
        view = None
        if isinstance(model, components.Componentized):
            view = model.getAdapter(interfaces.IView)
        if not view and hasattr(model, '__class__'):
            view = interfaces.IView(model, None)
        
        if view:
            view["id"] = self.attributes.get('id', '')
            view.templateNode = node
            view.controller = self.controller
            return view.setDataCallback(result, request, node)
        else:
            return Widget.setDataCallback(self, result, request, node)


class Break(Widget):
    """Break into pdb when this widget is rendered. Mildly
    useful for debugging template structure, model stacks,
    etc.
    """
    def setUp(self, request, node, data):
        import pdb; pdb.set_trace()


view.registerViewForModel(Text, model.StringModel)
view.registerViewForModel(List, model.ListModel)
view.registerViewForModel(KeyedList, model.DictionaryModel)
view.registerViewForModel(Link, model.Link)
view.registerViewForModel(DeferredWidget, model.DeferredWrapper)
