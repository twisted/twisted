# -*- test-case-name: twisted.test.test_woven -*-
#
# WORK IN PROGRESS: HARD HAT REQUIRED
# 

from __future__ import nested_scopes

# Twisted Imports

from twisted.python import formmethod, failure
from twisted.python.components import registerAdapter, getAdapter
from twisted.web import domhelpers, resource
from twisted.internet import defer

# Sibling Imports
from twisted.web.woven import model, view, controller, widgets, input, interfaces, tapestry

from twisted.web.microdom import parseString, lmx


# map formmethod.Argument to functions that render them:
_renderers = {}

def registerRenderer(argumentClass, renderer):
    """Register a renderer for a given argument class.

    The renderer function should act in the same way
    as the 'input_XXX' methods of C{FormFillerWidget}.
    """
    assert callable(renderer)
    global _renderers
    _renderers[argumentClass] = renderer

    
def getValue(request, argument):
    """Return value for form inpurt."""
    values = request.args.get(argument.name, None)
    if values:
        try:
            return argument.coerce(values[0])
        except formmethod.InputError:
            return values[0]
    return argument.default


def getValues(request, argument):
    """Return values for form inpurt."""
    values = request.args.get(argument.name, None)
    if values:
        try:
            return argument.coerce(values)
        except formmethod.InputError:
            return values
    return argument.default


class FormFillerWidget(widgets.Widget):

    def createShell(self, request, node, data):
        """Create a `shell' node that will hold the additional form elements, if one is required.
        """
        return lmx(node).table(border="0")
    
    def input_single(self, request, content, arg):
        value = getValue(request, arg)
        if value == None:
            value = ""
        else:
            value = str(value)
        return content.input(type="text",
                             size="60",
                             name=arg.name,
                             value=value)

    def input_text(self, request, content, arg):
        r = content.textarea(cols="60",
                             rows="10",
                             name=arg.name,
                             wrap="virtual")
        r.text(str(getValue(request, arg)))
        return r

    input_integer = input_single
    input_string = input_single
    input_float = input_single

    def input_choice(self, request, content, arg):
        s = content.select(name=arg.name)
        default = getValue(request, arg)
        for tag, value, desc in arg.choices:
            if value == default:
                kw = {'selected' : '1'}
            else:
                kw = {}
            s.option(value=tag, **kw).text(desc)
        return s

    def input_radiogroup(self, request, content, arg):
        s = content.div()
        defaults = getValues(request, arg)
        for tag, value, desc in arg.choices:
            if value in defaults:
                kw = {'checked' : '1'}
            else:
                kw = {}
            s.div().input(name=arg.name,
                          type="radio", **kw).text(desc)
        return s

    def input_checkgroup(self, request, content, arg):
        s = content.div()
        defaults = getValues(request, arg)
        for tag, value, desc in arg.choices:
            if value in defaults:
                kw = {'checked' : '1'}
            else:
                kw = {}
            s.input(type="checkbox",
                    name=arg.name,
                    value=tag, **kw).text(desc)
        return s

    def input_boolean(self, request, content, arg):
        if getValue(request, arg):
            kw = {'checked' : '1'}
        else:
            kw = {}
        i = content.input(type="checkbox",
                          name=arg.name, **kw)
        return i

    def input_password(self, request, content, arg):
        return content.input(type="password",
                             size="60",
                             name=arg.name)

    def input_flags(self, request, content, arg):
        defaults = getValues(request, arg)
        for key, val, label in arg.flags:
            if val in defaults:
                kw = {'checked' : '1'}
            else:
                kw = {}
            nn = content.input(type="checkbox",
                               name=arg.name,
                               value=str(key), **kw)
            nn.text(label)
        return content

    def input_hidden(self, request, content, arg):
        return content.input(type="hidden",
                             name=arg.name,
                             value=getValue(request, arg))

    def input_submit(self, request, content, arg):
        div = content.div()
        for tag, value, desc in arg.choices:
            div.input(type="submit", name=arg.name, value=tag)
            div.text(" ")
        if arg.reset:
            div.input(type="reset")
        return div

    def input_date(self, request, content, arg):
        date = getValues(request, arg)
        if date == None:
            year, month, day = "", "", ""
        else:
            year, month, day = date
        div = content.div()
        div.text("Year: ")
        div.input(type="text", size="4", maxlength="4", name=arg.name, value=str(year))
        div.br()
        div.text("Month: ")
        div.input(type="text", size="2", maxlength="2", name=arg.name, value=str(month))
        div.br()
        div.text("Day: ")
        div.input(type="text", size="2", maxlength="2", name=arg.name, value=str(day))
        return div
    
    def createInput(self, request, shell, arg):
        name = arg.__class__.__name__.lower()
        if _renderers.has_key(arg.__class__):
            imeth = _renderers[arg.__class__]
        else:
            imeth = getattr(self,"input_"+name)
        if name == "hidden":
            return (imeth(request, shell, arg).node, lmx())
        elif name == "submit":
            td = shell.tr().td(valign="top", colspan="2")
            return (imeth(request, td, arg).node, lmx())
        else:
            tr = shell.tr()
            tr.td(align="right", valign="top").text(arg.getShortDescription()+":")
            content = tr.td(valign="top")
            return (imeth(request, content, arg).node,
                    content.div(style="color: green").
                    text(arg.getLongDescription()).node)

    def setUp(self, request, node, data):
        # node = widgets.Widget.generateDOM(self,request,node)
        lmn = lmx(node)
        if not node.hasAttribute('action'):
            lmn['action'] = (request.prepath+request.postpath)[-1]
        if not node.hasAttribute("method"):
            lmn['method'] = 'post'
        lmn['enctype'] = 'multipart/form-data'
        self.errorNodes = errorNodes = {}                     # name: nodes which trap errors
        self.inputNodes = inputNodes = {}
        for errorNode in domhelpers.findElementsWithAttribute(node, 'errorFor'):
            errorNodes[errorNode.getAttribute('errorFor')] = errorNode
        argz={}
        # list to figure out which nodes are in the template already and which aren't
        hasSubmit = 0
        argList = self.model.fmethod.getArgs()
        for arg in argList:
            if isinstance(arg, formmethod.Submit):
                hasSubmit = 1
            argz[arg.name] = arg
        inNodes = domhelpers.findElements(
            node,
            lambda n: n.tagName.lower() in ('textarea', 'select', 'input'))
        for inNode in inNodes:
            t = inNode.getAttribute("type")
            if t and t.lower() == "submit":
                hasSubmit = 1
            nName = inNode.getAttribute("name")
            assert argz.has_key(nName), "signature does not define %r, but template has node %s" % (nName,inNode.toxml())
            inputNodes[nName] = inNode
            del argz[nName]
        if argz:
            shell = self.createShell(request, node, data)
            # create inputs, in the same order they were passed to us:
            for remArg in [arg for arg in argList if argz.has_key(arg.name)]:
                inputNode, errorNode = self.createInput(request, shell, remArg)
                errorNodes[remArg.name] = errorNode
                inputNodes[remArg.name] = inputNode

        if not hasSubmit:
            lmn.input(type="submit")


class FormErrorWidget(FormFillerWidget):
    def setUp(self, request, node, data):
        FormFillerWidget.setUp(self, request, node, data)
        for k, f in self.model.err.items():
            en = self.errorNodes[k]
            tn = self.inputNodes[k]
            for n in en, tn:
                n.setAttribute('style', "color: red")
            en.childNodes[:]=[] # gurfle, CLEAR IT NOW!@#
            if isinstance(f, failure.Failure):
                f = f.getErrorMessage()
            lmx(en).text(str(f))


class FormDisplayModel(model.MethodModel):
    def initialize(self, fmethod):
        self.fmethod = fmethod

class FormErrorModel(FormDisplayModel):
    def initialize(self, fmethod, args, err):
        FormDisplayModel.initialize(self, fmethod)
        self.args = args
        if isinstance(err, Exception):
            self.err = getattr(err, "descriptions", {})
            self.desc = err
        else:
            self.err = err
            self.desc = "Please try again"

    def wmfactory_description(self, request):
        return str(self.desc)


class ThankYou(view.View):
    template = '''
    <html>
    <head>
    <title> Thank You </title>
    </head>
    <body>
    <h1>Thank You for Using Woven</h1>
    <div model=".">
    </div>
    </body>
    </html>
    '''


class FormProcessor(resource.Resource):
    def __init__(self, formMethod, callback=None, errback=None):
        self.formMethod = formMethod
        if callback is None:
            callback = self.viewFactory
        self.callback = callback
        if errback is None:
            errback = self.errorViewFactory
        self.errback = errback

    def render(self, request):
        outDict = {}
        errDict = {}
        for methodArg in self.formMethod.getArgs():
            valmethod = getattr(self,"mangle_"+(methodArg.__class__.__name__.lower()), None)
            tmpval = request.args.get(methodArg.name)
            if valmethod:
                # mangle the argument to a basic datatype that coerce will like
                tmpval = valmethod(tmpval)
            # coerce it
            try:
                cv = methodArg.coerce(tmpval)
                outDict[methodArg.name] = cv
            except:
                errDict[methodArg.name] = failure.Failure()
        if errDict:
            # there were problems processing the form
            return self.errback(self.errorModelFactory(request.args, outDict, errDict)).render(request)
        else:
            try:
                outObj = self.formMethod.call(**outDict)
            except formmethod.FormException, e:
                err = request.errorInfo = self.errorModelFactory(request.args, outDict, e)
                return self.errback(err).render(request)
            else:
                if isinstance(outObj, defer.Deferred):
                    def _cbModel(result):
                        return self.callback(self.modelFactory(result))
                    def _ebModel(err):
                        if err.trap(formmethod.FormException):
                            mf = self.errorModelFactory(request.args, outDict, err.value)
                            return self.errback(mf)
                        raise err
                    outObj.addCallback(_cbModel).addErrback(_ebModel)
                    return tapestry._ChildJuggler(outObj).render(request)
                else:
                    return self.callback(self.modelFactory(outObj)).render(request)

    def errorModelFactory(self, args, out, err):
        return FormErrorModel(self.formMethod, args, err)

    def errorViewFactory(self, m):
        v = view.View(m)
        v.template = '''
        <html>
        <head>
        <title> Form Error View </title>
        </head>
        <body>
        Error: <span model="description" />
        <form model=".">
        </form>
        </body>
        </html>
        '''
        return v

    def modelFactory(self, outObj):
        adapt = getAdapter(outObj, interfaces.IModel, outObj)
        # print 'factorizing', adapt
        return adapt

    def viewFactory(self, model):
        # return getAdapter(model, interfaces.IView)
        return ThankYou(model)

    # mangliezrs

    def mangle_single(self, args):
        if args:
            return args[0]
        else:
            return ''

    mangle_string = mangle_single
    mangle_password = mangle_single
    mangle_text = mangle_single
    mangle_integer = mangle_single
    mangle_float = mangle_single
    mangle_choice = mangle_single
    mangle_boolean = mangle_single
    mangle_hidden = mangle_single
    mangle_submit = mangle_single
    
    def mangle_flags(self, args):
        if args is None:
            return []
        return args

from twisted.python.formmethod import FormMethod

view.registerViewForModel(FormFillerWidget, FormDisplayModel)
view.registerViewForModel(FormErrorWidget, FormErrorModel)
registerAdapter(FormDisplayModel, FormMethod, interfaces.IModel)

