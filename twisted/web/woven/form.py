
#
# WORK IN PROGRESS: HARD HAT REQUIRED
# 

# Twisted Imports

from twisted.python import formmethod, failure
from twisted.python.components import registerAdapter, getAdapter
from twisted.web import domhelpers, resource

# Sibling Imports
from twisted.web.woven import model, view, controller, widgets, input, interfaces

from twisted.web.microdom import parseString

class lmx:
    """
    
     ___   _     _____     _______ 
    |_ _| | |   |_ _\ \   / / ____|
     | |  | |    | | \ \ / /|  _|  
     | |  | |___ | |  \ V / | |___ 
    |___| |_____|___|  \_/  |_____|
    
    """
    createElement = widgets.document.createElement
    def __init__(self, node):
        self.node = node
    def __getattr__(self, name):
        if name[0] == '_':
            raise AttributeError("no private attrs")
        return lambda **kw: self.add(name,**kw)
    def __setitem__(self, key, val):
        self.node.setAttribute(key, val)
    def text(self, txt):
        nn = widgets.document.createTextNode(txt)
        self.node.appendChild(nn)
        return self
    def add(self, tagName, **kw):
        newNode = self.createElement(tagName)
        self.node.appendChild(newNode)
        xf = lmx(newNode)
        for k, v in kw.items():
            xf[k]=v
        return xf

class FormFillerWidget(widgets.Widget):

    def createShell(self, request, node, data):
        """Create a `shell' node that will hold the additional form elements, if one is required.
        """
        return lmx(node).table(border="0")

    def createInput(self, request, shell, arg):
        tr = shell.tr()
        tr.td(align="right", valign="top").text(arg.getShortDescription()+":")
        body = tr.td(valign="top")
        return (body.input(type="text", name=arg.name).node,
                body.div(style="color: green").
                text(arg.getLongDescription()).node)

    def setUp(self, request, node, data):
        # node = widgets.Widget.generateDOM(self,request,node)
        lmn = lmx(node)
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
        self.err = err


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
    def __init__(self, formMethod):
        self.formMethod = formMethod

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
            return self.errorViewFactory(self.errorModelFactory(request.args, outDict, errDict)).render(request)
        else:
            outObj = self.formMethod.call(**outDict)
            return self.viewFactory(self.modelFactory(outObj)).render(request)

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
        <form model=".">
        </form>
        </body>
        </html>
        '''
        return v

    def modelFactory(self, outObj):
        return getAdapter(outObj, interfaces.IModel)

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
    mangle_integer = mangle_single
    mangle_float = mangle_single
    mangle_choice = mangle_single
    mangle_boolean = mangle_single

    def mangle_flags(self, args):
        if arg is None:
            return []
        return arg

from twisted.python.formmethod import FormMethod

view.registerViewForModel(FormFillerWidget, FormDisplayModel)
view.registerViewForModel(FormErrorWidget, FormErrorModel)
registerAdapter(FormDisplayModel, FormMethod, interfaces.IModel)

