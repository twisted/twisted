

from twisted.web.woven import interfaces
from twisted.web.woven import widgets
from twisted.web.woven import model
from twisted.web.woven import page
from twisted.web.woven import controller
from twisted.web.woven.input import DictAggregator

from twisted.python import components

from twisted.web.microdom import lmx
from twisted.web.domhelpers import findElementsWithAttribute
from twisted.web import server
from twisted.web import static
from twisted.web import resource
from twisted.web import domhelpers
from twisted.web import microdom


from twisted.python import formmethod


class IWovenForms(components.Interface):
    """A mapping of form ids to form instances specific to
    this session.
    """


components.registerAdapter(lambda _: {}, server.Session, IWovenForms)


ERROR = 'A constant which indicates the most recent form which had an error.'


class FormPage(page.Page):
    def getDynamicChild(self, name, request):
        if name.startswith('woven_form_post-'):
            forms = request.getSession(IWovenForms)
            print "FORMS", forms
            formId = name.split('-')[1]
            form = forms[formId]
            del forms[formId]
            print "we just posted to a form, ", form
            print request.args
            self.formPosted = True
            ## We're posting a form instance
            ## Let's generate a DOM we can use
            ## to drive the input-validation process
            d = microdom.parseString('<html/>')
            content = d.childNodes[0]
            ## This will only show if we don't get redirected
            lmx(content).h3().text("Post success!")
            ## Use the templateNode from the form
            ## to drive input validation
            content.appendChild(form.templateNode)
            ## Tell ourself to find the dom we just created
            self.lookupTemplate = lambda request: d
            self.addSlash = 0
            return self


class FormWidget(widgets.Widget):
    formClass = None
    tagName = 'form'
    clearNode = 1
    def generate(self, request, node):
        forms = request.getSession(IWovenForms)
        error = forms.get(ERROR)
        if error is not None and forms[error].submodel == self.submodel:
            del forms[ERROR]
            ## We already generated the error DOM when we checked for errors
            return forms[error].node
        return widgets.Widget.generate(self, request, node)

    def setUp(self, request, node, data):
        forms = request.getSession(IWovenForms)
        forms[self.submodel] = self
        self.setAttribute('action', 'woven_form_post-%s' % self.submodel)

        body = self.getPattern('formBody', None)
        if body is not None:
            body.childNodes = []
            self.appendChild(body)
        else:
            body = request.d.createElement('table')
            self.appendChild(body)
        for arg in data.getArgs():
            name = arg.name
            new = self.getPattern(name, None)
            if new is None:
                new = self.getPattern('formItem', None)
            if new is None:
                new = request.d.createElement('tr')
            ## Check to see which model we should use; the form
            ## default, or the model on the model stack directly
            ## above the formmethod... kinda hacky
            new.setAttribute('model', name)
            body.appendChild(new)
        formSubmit = self.getPattern('formSubmit', None)
        if formSubmit is not None:
            body.appendChild(formSubmit)
        else:
            row = lmx(body).tr()
            row.td()
            row.td().input(type='submit', style='display: table-cell', align="right")
            row.td()


class FieldWidget(widgets.Widget):
    error = None
    def setError(self, request, error):
        self.error = error

    def getValue(self, request, data):
        filled = self.model.parent.parent.getSubmodel(request, data.name)
        if filled is not None:
            return filled.getData(request)
        if hasattr(data, 'value'):
            return data.value
        return data.default

    def setUp(self, request, node, data):
        l = lmx(self)
        existing = self.getPattern('fieldLabel', None, clone=False)
        if data.shortDesc:
            name = data.shortDesc
        else:
            name=data.name
        if existing:
            existing.childNodes = []
            lmx(existing).text(name)
        else:
            l.td().text(name)
        existing = findElementsWithAttribute(node, 'name', data.name)
        if not existing:
            existing = self.getPattern('fieldInput', None, clone=False)
            if existing is not None:
                existing = [existing]
        
        viewName = data.__class__.__name__.lower()
        
        if existing:
            existing[0].setAttribute('view', viewName)
            existing[0].setAttribute('name', str(data.name))
            existing[0].setAttribute('value', str(self.getValue(request, data)))
        else:
            l.td().input(view=viewName)
        
        desc = self.getPattern('fieldDescription', None, clone=False)
        if desc is None:
            desc = l.td()
        else:
            desc.childNodes = []
            desc = lmx(desc)
        desc.text(data.longDesc)

        err = self.getPattern('fieldError', None, clone=False)
        if err is None:
            err = l.td(style="color: red")
        else:
            err = lmx(err)
        if self.error:
            err.text("ERROR: "+self.error)

    def wvupdate_input(self, request, widget, data):
        widget.setAttribute('type', data.__class__.__name__.lower())
        widget.setAttribute('name', data.name)
        widget.setAttribute('value', str(self.getValue(request, data)))

    wvupdate_password = wvupdate_input
    wvupdate_hidden = wvupdate_input

    def wvupdate_string(self, request, widget, data):
        widget.setAttribute('name', data.name)
        widget.setAttribute('value', str(self.getValue(request, data)))

    wvupdate_integer = wvupdate_string
    wvupdate_float = wvupdate_string

    def wvupdate_text(self, request, widget, data):
        widget.tagName = 'textarea'
        widget.setAttribute('name', data.name)
        lmx(widget).text(str(self.getValue(request, data)))

    def wvupdate_choice(self, request, widget, data):
        widget.tagName = 'select'
        widget.setAttribute('name', data.name)
        l = lmx(widget)
        for i in range(len(data.choices)):
            choice = data.choices[i]
            if str(i) == str(self.getValue(request, data)):
                l.option(value=str(i), selected='selected').text(choice)
            else:
                l.option(value=str(i)).text(choice)


class FormModel(model.Model):
    def submodelCheck(self, request, name):
        for arg in self.original.getArgs():
            if arg.name == name:
                return True

    def submodelFactory(self, request, name):
        for arg in self.original.getArgs():
            if arg.name == name:
                return arg


class FieldModel(model.Model):
    pass


class FormController(DictAggregator):
    def __init__(self, *args, **kwargs):
        DictAggregator.__init__(self, *args, **kwargs)
        if self._commit is None:
            self._commit = self.success
        self._errback = self.error

    def error(self, request, *args, **kwargs):
        forms = request.getSession(IWovenForms)
        formId = self.view.submodel
        forms[formId] = self.view
        forms[ERROR] = formId
        from twisted.protocols import http
        request.setResponseCode(http.SEE_OTHER)
        request.setHeader("location", "./")

    def success(self, *args, **kwargs):
        print "CONTROLLER COMMIT", args, kwargs
        self.model.original.call(**kwargs)


class FieldController(controller.Controller):
    def handle(self, request):
        filled = self.model.original
        data = request.args.get(filled.name, [None])[0]
        if data is None:
            return
        
        try:
            filled.coerce(data)
        except (formmethod.InputError, formmethod.FormException), e:
            print "ERRO!",e
            self.view.setError(request, str(e))
            self._parent.aggregateInvalid(request, self, data)
            return

        filled.value = data
        self._parent.aggregateValid(request, self, data)

    def commit(self, *args, **kwargs):
        print "FIELD COMMIT"


components.registerAdapter(FormModel, formmethod.FormMethod, interfaces.IModel)
components.registerAdapter(FieldModel, formmethod.Argument, interfaces.IModel)

components.registerAdapter(FormWidget, FormModel, interfaces.IView)
components.registerAdapter(FormController, FormModel, interfaces.IController)

components.registerAdapter(FieldWidget, FieldModel, interfaces.IView)
components.registerAdapter(FieldController, FieldModel, interfaces.IController)

