"""
STAN -- Stan Template Acceleration Nexus
"""
from __future__ import generators
import types
from twisted.web import html
from types import StringTypes
from twisted.web.woven import interfaces, model
from twisted.python import components, failure
from twisted.python.components import implements
from twisted.internet import reactor, defer
from cStringIO import StringIO
import sys

def keyGenerator():
    x = 0
    while 1:
        x += 1
        yield x

generateKey = keyGenerator().next


def simplify(seq, indent='  '):
    lst = []
    strjoin = ''.join
    indentlevel = 0
    for x in seq:
        if isinstance(x, (IndentPush, IndentPop)):
            continue
        if isinstance(x, StringTypes):
            lst.append(x)
        else:
            if lst:
                yield strjoin(lst)
                del lst[:]
            yield x
    if lst:
        yield strjoin(lst)


class IStanInstruction(components.Interface):
    """An object which modifies the current stan virtual machine state.
    """
    def operate(state):
        pass


class IStanExpandable(components.Interface):
    """An object which expands to a list of stan instructions to process.
    """
    def generate():
        pass


class XMLAbomination(object):
    """This is the magic XML tag prototype factory
    You can create tag prototypes like:
        x = XMLAbomination()
        x.html
        x('html')
        x['html']
    Choose your poison.
    """
    def __repr__(self):
        return 'XMLAbomination()'
        
    def __call__(self, name):
        assert isinstance(name, StringTypes)
        return XMLAbominationTagPrototype(name)

    def __getitem__(self, item):
        assert isinstance(item, StringTypes)
        return XMLAbominationTagPrototype(name)

    def __getattr__(self, name):
        if name.endswith('_') or name.startswith('__'):
            raise AttributeError, name
        elif name.startswith('_'):
            name = name[1:]
        return XMLAbominationTagPrototype(name)


class XMLAbominationTagPrototype(object):
    """This is the magic XML tag prototype
    You can create pretags like:
        nudebody = XMLAbomination().body
        nakedbody = XMLAbominationTagPrototype('body')
        clothedbody = nakedbody(bgcolor='red')
        darkbody = nakedbody({'bgcolor':'black'})
        greenbody = XMLAbominationTagPrototype('body', bgcolor='green')
        bluebody = XMLAbominationTagPrototype('body', {'bgcolor':'blue'})
    Tags are created using ['blah!'] context with something in them.
    This is done implicitly by the parent if necessary.
    """  
        
    def __init__(self, name, **kwargs):
        self.name = name
        self.attributes = [
            Attribute(k, v) for (k, v) in kwargs.items()
        ]

    def __call__(self, *args, **kwargs):
        if not kwargs and len(args) == 1:
            return XMLAbominationTagPrototype(self.name, **args[0])
        return XMLAbominationTagPrototype(self.name, **kwargs)
    
    def children(self, *items):
        items = [(not (isinstance(x, XMLAbominationTagPrototype)) and x or x.children()) for x in items]
        return Tag(self.name, self.attributes, items) 

    def with(self, **kwargs):
        return TagWith(self, **kwargs)
    
    def __getitem__(self, items):
        if not isinstance(items, (list, tuple)):
            items = [items]
        return self.children(*items)
    
    def __repr__(self):
        return '<XMLAbominationTagPrototype name=%r id=%s attributes=%r>' % (self.name, hex(id(self)), self.attributes)


class Tag(object):
    __implements__ = IStanExpandable,
    def __init__(self, name, attributes, items):
        self.name = name
        self.attributes = attributes
        self.children = items
    
    def generate(self):
        key = generateKey()
        yield '<' + self.name
        for attribute in self.attributes:
            for chunk in attribute.generate():
                yield chunk
        if not self.children:
            yield '/>'
            return
        yield '>'
        yield IndentPush(key)
        for child in self.children:
            if components.implements(child, IStanExpandable):
                for chunk in child.generate():
                    yield chunk
            else:
                yield child
        yield IndentPop(key)
        yield '</'
        yield self.name
        yield '>'
        
    def __repr__(self):
        return '<Tag name=%r id=%s attributes=%r len(children)=%d>' % (self.name, hex(id(self)), self.attributes, len(self.children))


class _Nothing(object):
    pass


class TagWith(object):
    __implements__ = IStanExpandable,
    def __init__(self, tag, model=_Nothing, view=_Nothing, pattern=_Nothing):
        self.tag = tag
        self.model = model
        self.view = view
        self.pattern = pattern

    def children(self, *items):
        self.tag = self.tag.children(*items)
        return self

    def __getitem__(self, items):
        if not isinstance(items, (list, tuple)):
            items = [items]
        return self.children(*items)
        
    def __call__(self, model, callstack, viewstack):
        pass
    
    def generate(self):
        pops = []
        if self.model is not _Nothing or self.view is not _Nothing:
            key = generateKey()
            pops.append(Popper(key))
            if self.view is _Nothing:
                self.view = View(key)
            elif callable(self.view):
                self.view = self.view(key)
            else:
                ## it's a string; look for a view factory
                ## xxx not implemented yet
                self.view = View(key)
            yield Pusher(key, model=self.model, view=self.view)
        yield self.tag
        while pops:
            yield pops.pop()


class Attribute(object):
    __implements__ = IStanExpandable,
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def generate(self):
        yield ' '
        yield self.name
        yield '="'
        yield self.value
        yield '"'

    def __repr__(self):
        return 'Attribute(%s, %r)' % (self.name, self.value)


class View(object):
    def __init__(self, key, collected = None):
        self.key = key
        if collected is None:
            self.collected = []
        else:
            self.collected = collected
        self._updaters = [self.update]

    def __call__(self, **kwargs):
        self.attributes.update(kwargs)

    def __getitem__(self, items):
        if not isinstance(items, (list, tuple)):
            items = [items]
        self.children.extend(items)
        return self.children

    def update(self, model):
        """The view is being rendered against the given model;
        this method should use self.__call__ and self.__getitem__
        (as though self were an XMLAbomination)
        to influence how this node is going to look.
        """
        pass

    def generate(self, model):
        print "view generated", model, self.collected
        self.children = []
        self.attributes = {}
        for updater in self._updaters:
            updater(model)
        new = self.collected[0](**self.attributes)[self.children]
        for chunk in new.generate():
            yield chunk

    def collect(self, something):
        if self.collected:
            return something
        print "view collecting", something
        self.collected.append(something)


class StanInstruction(object):
    __implements__ = IStanInstruction
    def operate(self, state):
        print "operate", self


class Pusher(StanInstruction):
    def __init__(self, key, model=None, view=None, controller=None):
        self.key = key
        self.model = model
        self.view = view
        self.controller = controller

    def __repr__(self):
        return 'Pusher(%r, %r, %r, %r)' % (self.key, self.model, self.view, self.controller)

    def operate(self, state):
        StanInstruction.operate(self, state)
        state['views'].append(self.view)
        model = state['models'][-1].getSubmodel(self.model)
        state['models'].append(model)
        state['collectors'].append(self.view.collect)


class Popper(StanInstruction):
    def __init__(self, key):
        self.key = key
    
    def __repr__(self):
        return 'Popper(%r)' % self.key

    def operate(self, state):
        StanInstruction.operate(self, state)
        view = state['views'].pop()
        model = state['models'].pop()
        state['collectors'].pop()
        return view.generate(model.getData())


class IndentPush(StanInstruction):
    def __init__(self, key):
        self.key = key

    def __repr__(self):
        return 'IndentPush(%r)' % (self.key,)


class IndentPop(StanInstruction):
    def __init__(self, key):
        self.key = key

    def __repr__(self):
        return 'IndentPop(%r)' % (self.key,)


"""
class CondIf:
    __implements__ = IStanInstruction,
    def __init__(self, callable, key):
        self.callable = callable
        self.key = key

    def __repr__(self):
        return '<CondIf callable=%r key=%r>' % (self.callable, self.key)

class CondIfEnd:
    __implements__ = IStanInstruction,
    def __init__(self, callable, key):
        self.callable = callable
        self.key = key

    def __repr__(self):
        return '<CondIfEnd callable=%r key=%r>' % (self.callable, self.key)
        
class IterBegin:
    __implements__ = IStanInstruction,
    def __init__(self, seq, key):
        self.seq = seq
        self.key = key

    def __repr__(self):
        return '<IterBegin seq=%r key=%r>' % (self.seq, self.key)

class IterEnd:
    __implements__ = IStanInstruction,
    def __init__(self, seq, key):
        self.seq = seq
        self.key = key

    def __repr__(self):
        return '<IterEnd seq=%r key=%r>' % (self.seq, self.key)

"""

"""
components.registerAdapter(StanAttribute, None, IStanAttribute)
components.registerAdapter(StanAttributeStr, str, IStanAttribute)
components.registerAdapter(StanAttributeInt, int, IStanAttribute)
components.registerAdapter(StanIterableUnrenderedXML, XMLAbomination, IStanIterable)
components.registerAdapter(StanIterableXML, RenderableXMLAbomination, IStanIterable)
components.registerAdapter(StanIterableStr, str, IStanIterable)
components.registerAdapter(StanIterableForEach, ForEach, IStanIterable)
components.registerAdapter(StanIterableWithModel, WithModeler, IStanIterable)
components.registerAdapter(SomeView, model.StringModel, interfaces.IView)
"""


class Driver(object):
    def __init__(self, instructions, model):
        if not isinstance(instructions, types.GeneratorType):
            instructions = iter(instructions)
        self.instructions = instructions
        self.model = components.getAdapter(
            model, 
            interfaces.IModel, 
            None, 
            components.getAdapterClassWithInheritance)

    def render(self, request):
        viewstack, modelstack = [], [self.model]
        instructionstack = []
        instructions = self.instructions
        collector = []
        self.done = 0
        state = {
                    'views': viewstack, 
                    'models': modelstack,
                    'collectors': collector}
        while not self.done:
            try:
                opcode = instructions.next()
            except StopIteration:
                if instructionstack:
                    print "popping instruction stack", instructionstack
                    instructions = instructionstack.pop()
                    continue
                else:
                    print "done!"
                    self.done = 1
                    continue
            if collector:
                opcode = collector[-1](opcode)
            if isinstance(opcode, StringTypes):
                request.write(opcode)
            elif implements(opcode, IStanInstruction):
                result = opcode.operate(state)
                if result is not None:
                    ## The instruction wanted to perform more instructions
                    ## ie we expanded a macro
                    instructionstack.append(instructions)
                    instructions = result
                    ## handle these instructions before exhausting the original generator


class Text(View):
    def update(self, model):
        self[
            str(model)
        ]


if __name__ == '__main__':
    print ''
    print ''

    x = XMLAbomination()
    simpleDoc = (
        x.html[
            x.head[
                x.title['A simple doc']
            ],
            x.body(style='awesome')[
                x.h1['html sux'],
                x.h2.with(model='name', view=Text),
            ]
        ]
    )

    indent = 0

    print ''
    print ''

    one = {
        'name': 'fred',
    }

    condensed = list(simplify(simpleDoc.generate()))
    print "condensed", condensed
    driver = Driver(condensed, one)
    request = StringIO()
    driver.render(request)
    print "one", request.getvalue()

    print ''
    print ''
    
    two = {
        'name': 'bob'
    }

    driver = Driver(condensed, two)
    request = StringIO()
    driver.render(request)
    print "two", request.getvalue()


    from twisted.web import resource
    from twisted.web import server
    from twisted.internet import reactor

    class Tester(resource.Resource):
        def getChild(self, name, request):
            return self

        def render(self, request):
            if request.args.has_key('name'):
                driver = Driver(condensed, {'name': request.args['name'][0]})
                driver.render(request)
                request.finish()
                return server.NOT_DONE_YET
            return """
<html><body>
<form action="">
<input type="text" name="name" />
<input type="submit" />
</form>
</body></html>
"""

    site = server.Site(Tester())
    from twisted.internet import reactor
    reactor.listenTCP(8081, site)
    reactor.run()
