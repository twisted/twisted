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


class FormFillerWidget(widgets.Widget):

    def createShell(self, request, node, data):
        """Create a `shell' node that will hold the additional form elements, if one is required.
        """
        return lmx(node).table(border="0")
    
    def input_single(self, request, content, arg):
        return content.input(type="text",
                             size="60",
                             name=arg.name,
                             value=str(arg.default))

    def input_text(self, request, content, arg):
        r = content.textarea(cols="60",
                             rows="10",
                             name=arg.name,
                             wrap="virtual")
        r.text(str(arg.default))
        return r

    input_integer = input_single
    input_string = input_single
    input_float = input_single

    def input_choice(self, request, content, arg):
        s = content.select(name=arg.name)
        for tag, value, desc in arg.choices:
            if tag == arg.default:
                kw = {'selected' : '1'}
            else:
                kw = {}
            s.option(value=tag, **kw).text(desc)
        return s

    def input_radiogroup(self, request, content, arg):
        s = content.div()
        for tag, value, desc in arg.choices:
            if tag in arg.default:
                kw = {'checked' : '1'}
            else:
                kw = {}
            s.div().input(name=arg.name,
                          type="radio", **kw).text(desc)
        return s

    def input_checkgroup(self, request, content, arg):
        s = content.div()
        for tag, value, desc in arg.choices:
            if tag in arg.default:
                kw = {'checked' : '1'}
            else:
                kw = {}
            s.input(type="checkbox",
                    name=arg.name,
                    value=tag, **kw).text(desc)
        return s

    def input_boolean(self, request, content, arg):
        if arg.default:
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
        for key, val, label in arg.flags:
            if key in arg.default:
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
                             value=arg.default)
    
    def createInput(self, request, shell, arg):
        name = arg.__class__.__name__.lower()
        imeth = getattr(self,"input_"+name)
        if name == "hidden":
            return (imeth(request, shell, arg).node, lmx())
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
        lmn['method'] = 'post'
        lmn['enctype'] = 'multipart/form-data'
        self.errorNodes = errorNodes = {}                     # name: nodes which trap errors
        self.inputNodes = inputNodes = {}
        for errorNode in domhelpers.findElementsWithAttribute(node, 'errorFor'):
            errorNodes[errorNode.getAttribute('errorFor')] = errorNode
        argz={}
        # list to figure out which nodes are in the template already and which aren't
        for arg in self.model.fmethod.getArgs():
            argz[arg.name] = arg
        for inNode in domhelpers.getElementsByTagName(node, 'input'):
            nName = inNode.getAttribute("name")
            assert argz.has_key(nName), "method signature %s does not define argument %s" % (self.model.original, nName)
            inputNodes[nName] = inNode
            del argz[nName]
        if argz:
            shell = self.createShell(request, node, data)
            for remArg in argz.values():
                inputNode, errorNode = self.createInput(request, shell, remArg)
                errorNodes[remArg.name] = errorNode
                inputNodes[remArg.name] = inputNode
        # web browsers are wonky
        if len(inputNodes) > 1:
            # TODO: 'submit' hint to make a list of multiple buttons
            # clear button
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
            lmx(en).text(f.getErrorMessage())


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

    def wmfactory_description(self):
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
    
    def mangle_flags(self, args):
        if args is None:
            return []
        return args

from twisted.python.formmethod import FormMethod

view.registerViewForModel(FormFillerWidget, FormDisplayModel)
view.registerViewForModel(FormErrorWidget, FormErrorModel)
registerAdapter(FormDisplayModel, FormMethod, interfaces.IModel)

