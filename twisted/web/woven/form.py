
#
# WORK IN PROGRESS: HARD HAT REQUIRED
# 

# Twisted Imports

from twisted.python import formmethod, failure
from twisted.python.components import registerAdapter, getAdapter
from twisted.web import domhelpers

# Sibling Imports
import model, view, controller, widgets, input, interfaces

class FormWidget(widgets.Widget):
    def setUp(self, request, node, data):
        # node = widgets.Widget.generateDOM(self,request,node)
        inputNodes = domhelpers.getElementsByTagName(node, 'input')
        argz={}
        for arg in self.model.original.signature.methodSignature:
            argz[arg.name] = arg
        for inNode in inputNodes:
            nName = inNode.getAttribute("name")
            assert argz.has_key(nName), "method signature %s does not define argument %s" % (self.model.original, nName)
            del argz[nName]

        for remArg in argz.values():
            newnode = widgets.document.createElement("input")
            newnode.setAttribute("name", remArg.name)
            newnode.setAttribute("model", remArg.name)
            newnode.setAttribute("controller", remArg.name)
            node.appendChild(newnode)

class FieldModel(model.AttributeModel):
    def initialize(self, original):
        self.original = original


class FormModel(model.AttributeModel):
    def initialize(self, original):
        self.original = original

    def submodelFactory(self, name):
        print 'smf',`name`
        return FieldModel(self.original.signature.getArgument(name))

class FormFieldHandler(input.InputHandler):
    def commit(self, request, node, data):
        print 'no-op form commit'

    def getInput(self, request):
        try:
            self.coerce(request.args.get(self.name))
        except:
            self.checkError = failure.Failure()

    def check(self, request, data):
        print 'FormFieldHandler.check'
        if hasattr(self,'checkError'):
            return 0
        else:
            return 1

    def handleInvalid(self, request, data):
        self.invalidErrorText = self.checkError.getErrorMessage()

controller.registerControllerForModel(FormFieldHandler, FieldModel)

class StringInputHandler(input.InputHandler):
    def coerce(self, data):
        assert len(data) == 0, "Too Many Arguments."
        return str(data[0])

class FormController(input.InputHandler):
    def getSubcontroller(self, request, node, model, controllerName):
        ic = getAdapter(model, interfaces.IController, None)
        ic._parent = self
        ic.name = controllerName
        print 'gsc',`controllerName`,`model`,`ic`
        return ic

    def process(self, request, **data):
        print 'it is teh commiterry', data

    def check(self, request, data):
        print 'FormController.check', data
        return 1

# MVC triad for methods
registerAdapter(FormModel, formmethod.SignedMethod, interfaces.IModel)
view.registerViewForModel(FormWidget, FormModel)
controller.registerControllerForModel(FormController, FormModel)
