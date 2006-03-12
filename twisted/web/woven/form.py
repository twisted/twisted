# -*- test-case-name: twisted.web.test.test_woven -*-
#
# WORK IN PROGRESS: HARD HAT REQUIRED
# 

from __future__ import nested_scopes

# Twisted Imports

from twisted.python import formmethod, failure
from twisted.python.components import registerAdapter
from twisted.web import domhelpers, resource, util
from twisted.internet import defer

# Sibling Imports
from twisted.web.woven import model, view, controller, widgets, input, interfaces

from twisted.web.microdom import parseString, lmx, Element


#other imports
import math

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

    
class FormFillerWidget(widgets.Widget):

    SPANNING_TYPES = ["hidden", "submit"]
    
    def getValue(self, request, argument):
        """Return value for form input."""
        if not self.model.alwaysDefault:
            values = request.args.get(argument.name, None)
            if values:
                try:
                    return argument.coerce(values[0])
                except formmethod.InputError:
                    return values[0]
        return argument.default

    def getValues(self, request, argument):
        """Return values for form input."""
        if not self.model.alwaysDefault:
            values = request.args.get(argument.name, None)
            if values:
                try:
                    return argument.coerce(values)
                except formmethod.InputError:
                    return values
        return argument.default

    def createShell(self, request, node, data):
        """Create a `shell' node that will hold the additional form
        elements, if one is required.
        """
        return lmx(node).table(border="0")
    
    def input_single(self, request, content, model, templateAttributes={}):
        """
        Returns a text input node built based upon the node model.
        Optionally takes an already-coded DOM node merges that
        information with the model's information.  Returns a new (??)
        lmx node.
        """
        #in a text field, only the following options are allowed (well, more
        #are, but they're not supported yet - can add them in later)
        attribs = ['type', 'name', 'value', 'size', 'maxlength',
                   'readonly'] #only MSIE recognizes readonly and disabled

        arguments = {}
        for attrib in attribs:
            #model hints and values override anything in the template
            val = model.getHint(attrib, templateAttributes.get(attrib, None))
            if val:
                arguments[attrib] = str(val)
            
        value = self.getValue(request, model)
        if value:
            arguments["value"] = str(value)

        arguments["type"] = "text"  #these are default
        arguments["name"] = model.name

        return content.input(**arguments)

    def input_string(self, request, content, model, templateAttributes={}):
        if not templateAttributes.has_key("size"):
            templateAttributes["size"] = '60'
        return self.input_single(request, content, model, templateAttributes)

    input_integer = input_single
    input_integerrange = input_single
    input_float = input_single

    def input_text(self, request, content, model, templateAttributes={}):
        r = content.textarea(
            cols=str(model.getHint('cols',
                                   templateAttributes.get('cols', '60'))),
            rows=str(model.getHint('rows',
                                   templateAttributes.get('rows', '10'))),
            name=model.name,
            wrap=str(model.getHint('wrap',
                                   templateAttributes.get('wrap', "virtual"))))
        r.text(str(self.getValue(request, model)))
        return r

    def input_hidden(self, request, content, model, templateAttributes={}):
        return content.input(type="hidden",
                             name=model.name,
                             value=str(self.getValue(request, model)))

    def input_submit(self, request, content, model, templateAttributes={}):
        arguments = {}
        val = model.getHint("onClick", templateAttributes.get("onClick", None))
        if val:
            arguments["onClick"] = val
        arguments["type"] = "submit"
        arguments["name"] = model.name
        div = content.div()
        for tag, value, desc in model.choices:
            args = arguments.copy()
            args["value"] = tag
            div.input(**args)
            div.text(" ")
        if model.reset:
            div.input(type="reset")
        return div

    def input_choice(self, request, content, model, templateAttributes={}):
        # am I not evil? allow onChange js events
        arguments = {}
        val = model.getHint("onChange", templateAttributes.get("onChange", None))
        if val:
            arguments["onChange"] = val
        arguments["name"] = model.name
        s = content.select(**arguments)
        default = self.getValues(request, model)
        for tag, value, desc in model.choices:
            kw = {}
            if value in default:
                kw = {'selected' : '1'}
            s.option(value=tag, **kw).text(desc)
        return s

    def input_group(self, request, content, model, groupValues, inputType,
                    templateAttributes={}):
        """
        Base code for a group of objects.  Checkgroup will use this, as
        well as radiogroup.  In the attributes, rows means how many rows
        the group should be arranged into, cols means how many cols the
        group should be arranged into.  Columns take precedence over
        rows: if both are specified, the output will always generate the
        correct number of columns.  However, if the number of elements
        in the group exceed (or is smaller than) rows*cols, then the
        number of rows will be off.  A cols attribute of 1 will mean that
        all the elements will be listed one underneath another.  The
        default is a rows attribute of 1:  everything listed next to each
        other.
        """
        rows = model.getHint('rows', templateAttributes.get('rows', None))
        cols = model.getHint('cols', templateAttributes.get('cols', None))
        if rows:
            rows = int(rows)
        if cols:
            cols = int(cols)
            
        defaults = self.getValues(request, model)
        if (rows and rows>1) or (cols and cols>1):  #build a table
            s = content.table(border="0")
            if cols:
                breakat = cols
            else:
                breakat = math.ceil(float(len(groupValues))/rows)
            for i in range(0, len(groupValues), breakat):
                tr = s.tr()
                for j in range(0, breakat):
                    if i+j >= len(groupValues):
                        break
                    tag, value, desc = groupValues[i+j]
                    kw = {}
                    if value in defaults:
                        kw = {'checked' : '1'}
                    tr.td().input(type=inputType, name=model.name,
                        value=tag, **kw).text(desc)
                        
        else:
            s = content.div()
            for tag, value, desc in groupValues:
                kw = {}
                if value in defaults:
                    kw = {'checked' : '1'}
                s.input(type=inputType, name=model.name,
                        value=tag, **kw).text(desc)
                if cols:
                    s.br()

        return s

    def input_checkgroup(self, request, content, model, templateAttributes={}):
        return self.input_group(request, content, model, model.flags,
                                "checkbox", templateAttributes)

    def input_radiogroup(self, request, content, model, templateAttributes={}):
        return self.input_group(request, content, model, model.choices,
                                "radio", templateAttributes)

    #I don't know why they're the same, but they were.  So I removed the
    #excess code.  Maybe someone should look into removing it entirely.
    input_flags = input_checkgroup 

    def input_boolean(self, request, content, model, templateAttributes={}):
        kw = {}
        if self.getValue(request, model):
            kw = {'checked' : '1'}
        return content.input(type="checkbox", name=model.name, **kw)

    def input_file(self, request, content, model, templateAttributes={}):
        kw = {}
        for attrib in ['size', 'accept']:
            val = model.getHint(attrib, templateAttributes.get(attrib, None))
            if val:
                kw[attrib] = str(val)
        return content.input(type="file", name=model.name, **kw)

    def input_date(self, request, content, model, templateAttributes={}):
        breakLines = model.getHint('breaklines', 1)
        date = self.getValues(request, model)
        if date == None:
            year, month, day = "", "", ""
        else:
            year, month, day = date
        div = content.div()
        div.text("Year: ")
        div.input(type="text", size="4", maxlength="4", name=model.name, value=str(year))
        if breakLines:
            div.br()
        div.text("Month: ")
        div.input(type="text", size="2", maxlength="2", name=model.name, value=str(month))
        if breakLines:
            div.br()
        div.text("Day: ")
        div.input(type="text", size="2", maxlength="2", name=model.name, value=str(day))
        return div

    def input_password(self, request, content, model, templateAttributes={}):
        return content.input(
            type="password",
            size=str(templateAttributes.get('size', "60")),
            name=model.name)

    def input_verifiedpassword(self, request, content, model, templateAttributes={}):
        breakLines = model.getHint('breaklines', 1)
        values = self.getValues(request, model)
        if isinstance(values, (str, unicode)):
            values = (values, values)
        if not values:
            p1, p2 = "", ""
        elif len(values) == 1:
            p1, p2 = values, ""
        elif len(values) == 2:
            p1, p2 = values
        else:
            p1, p2 = "", ""
        div = content.div()
        div.text("Password: ")
        div.input(type="password", size="20", name=model.name, value=str(p1))
        if breakLines:
            div.br()
        div.text("Verify: ")
        div.input(type="password", size="20", name=model.name, value=str(p2))
        return div


    def convergeInput(self, request, content, model, templateNode):
        name = model.__class__.__name__.lower()
        if _renderers.has_key(model.__class__):
            imeth = _renderers[model.__class__]
        else:
            imeth = getattr(self,"input_"+name)

        return imeth(request, content, model, templateNode.attributes).node
    
    def createInput(self, request, shell, model, templateAttributes={}):
        name = model.__class__.__name__.lower()
        if _renderers.has_key(model.__class__):
            imeth = _renderers[model.__class__]
        else:
            imeth = getattr(self,"input_"+name)
        if name in self.SPANNING_TYPES:
            td = shell.tr().td(valign="top", colspan="2")
            return (imeth(request, td, model).node, shell.tr().td(colspan="2").node)
        else:
            if model.allowNone:
                required = ""
            else:
                required = " *"
            tr = shell.tr()
            tr.td(align="right", valign="top").text(model.getShortDescription()+":"+required)
            content = tr.td(valign="top")
            return (imeth(request, content, model).node, 
                    content.div(_class="formDescription"). # because class is a keyword
                    text(model.getLongDescription()).node)

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
            lambda n: n.tagName.lower() in ('textarea', 'select', 'input',
                                            'div'))
        for inNode in inNodes:
            t = inNode.getAttribute("type")
            if t and t.lower() == "submit":
                hasSubmit = 1
            if not inNode.hasAttribute("name"):
                continue
            nName = inNode.getAttribute("name")
            if argz.has_key(nName):
                #send an empty content shell - we just want the node
                inputNodes[nName] = self.convergeInput(request, lmx(),
                                                       argz[nName], inNode)
                inNode.parentNode.replaceChild(inputNodes[nName], inNode)
                del argz[nName]
            # TODO:
            # * some arg types should only have a single node (text, string, etc)
            # * some should have multiple nodes (choice, checkgroup)
            # * some have a bunch of ancillary nodes that are possible values (menu, radiogroup)
            # these should all be taken into account when walking through the template
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
            en.setAttribute('class', 'formError')
            tn.setAttribute('class', 'formInputError')
            en.childNodes[:]=[] # gurfle, CLEAR IT NOW!@#
            if isinstance(f, failure.Failure):
                f = f.getErrorMessage()
            lmx(en).text(str(f))


class FormDisplayModel(model.MethodModel):
    def initialize(self, fmethod, alwaysDefault=False):
        self.fmethod = fmethod
        self.alwaysDefault = alwaysDefault

class FormErrorModel(FormDisplayModel):
    def initialize(self, fmethod, args, err):
        FormDisplayModel.initialize(self, fmethod)
        self.args = args
        if isinstance(err, failure.Failure):
            err = err.value
        if isinstance(err, Exception):
            self.err = getattr(err, "descriptions", {})
            self.desc = err
        else:
            self.err = err
            self.desc = "Please try again"

    def wmfactory_description(self, request):
        return str(self.desc)

class _RequestHack(model.MethodModel):
    def wmfactory_hack(self, request):
        rv = [[str(a), repr(b)] for (a, b)
              in request._outDict.items()]
        #print 'hack', rv
        return rv

class FormProcessor(resource.Resource):
    def __init__(self, formMethod, callback=None, errback=None):
        resource.Resource.__init__(self)
        self.formMethod = formMethod
        if callback is None:
            callback = self.viewFactory
        self.callback = callback
        if errback is None:
            errback = self.errorViewFactory
        self.errback = errback

    def getArgs(self, request):
        """Return the formmethod.Arguments.

        Overridable hook to allow pre-processing, e.g. if we want to enable
        on them depending on one of the inputs.
        """
        return self.formMethod.getArgs()
    
    def render(self, request):
        outDict = {}
        errDict = {}
        for methodArg in self.getArgs(request):
            valmethod = getattr(self,"mangle_"+
                                (methodArg.__class__.__name__.lower()), None)
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
            return self.errback(self.errorModelFactory(
                request.args, outDict, errDict)).render(request)
        else:
            try:
                if self.formMethod.takesRequest:
                    outObj = self.formMethod.call(request=request, **outDict)
                else:
                    outObj = self.formMethod.call(**outDict)
            except formmethod.FormException, e:
                err = request.errorInfo = self.errorModelFactory(
                    request.args, outDict, e)
                return self.errback(err).render(request)
            else:
                request._outDict = outDict # CHOMP CHOMP!
                # I wanted better default behavior for debugging, so I could
                # see the arguments passed, but there is no channel for this in
                # the existing callback structure.  So, here it goes.
                if isinstance(outObj, defer.Deferred):
                    def _ebModel(err):
                        if err.trap(formmethod.FormException):
                            mf = self.errorModelFactory(request.args, outDict,
                                                        err.value)
                            return self.errback(mf)
                        raise err
                    (outObj
                     .addCallback(self.modelFactory)
                     .addCallback(self.callback)
                     .addErrback(_ebModel))
                    return util.DeferredResource(outObj).render(request)
                else:
                    return self.callback(self.modelFactory(outObj)).render(
                        request)

    def errorModelFactory(self, args, out, err):
        return FormErrorModel(self.formMethod, args, err)

    def errorViewFactory(self, m):
        v = view.View(m)
        v.template = '''
        <html>
        <head>
        <title> Form Error View </title>
        <style>
        .formDescription {color: green}
        .formError {color: red; font-weight: bold}
        .formInputError {color: #900}
        </style>
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
        adapt = interfaces.IModel(outObj, outObj)
        # print 'factorizing', adapt
        return adapt

    def viewFactory(self, model):
        # return interfaces.IView(model)
        if model is None:
            bodyStr = '''
            <table model="hack" style="background-color: #99f">
            <tr pattern="listItem" view="Widget">
            <td model="0" style="font-weight: bold">
            </td>
            <td model="1">
            </td>
            </tr>
            </table>
            '''
            model = _RequestHack()
        else:
            bodyStr = '<div model="." />'
        v = view.View(model)
        v.template = '''
        <html>
        <head>
        <title> Thank You </title>
        </head>
        <body>
        <h1>Thank You for Using Woven</h1>
        %s
        </body>
        </html>
        ''' % bodyStr
        return v

    # manglizers

    def mangle_single(self, args):
        if args:
            return args[0]
        else:
            return ''

    mangle_string = mangle_single
    mangle_text = mangle_single
    mangle_integer = mangle_single
    mangle_password = mangle_single
    mangle_integerrange = mangle_single
    mangle_float = mangle_single
    mangle_choice = mangle_single
    mangle_boolean = mangle_single
    mangle_hidden = mangle_single
    mangle_submit = mangle_single
    mangle_file = mangle_single
    mangle_radiogroup = mangle_single
    
    def mangle_multi(self, args):
        if args is None:
            return []
        return args

    mangle_checkgroup = mangle_multi
    mangle_flags = mangle_multi
    
from twisted.python.formmethod import FormMethod

view.registerViewForModel(FormFillerWidget, FormDisplayModel)
view.registerViewForModel(FormErrorWidget, FormErrorModel)
registerAdapter(FormDisplayModel, FormMethod, interfaces.IModel)

