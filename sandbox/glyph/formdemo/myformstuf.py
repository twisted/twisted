
from twisted.web.woven.page import Page
from twisted.web.woven.model import AttributeModel
from twisted.web.woven.form import FormProcessor
from twisted.python import formmethod as fm

formTestSignature = fm.MethodSignature(
    fm.String("arg1", "A default for arg1.",
              "Argument #1", "Hooray it is an argument."),
    fm.Password("arg2", "Some More Default",
                "Argument #2", "Your password."),
    fm.CheckGroup("arg3",
                  flags=[["one", 1, "Here is a flag, its value is 1"],
                         ["two", 2, "Here is another flag, 2."],
                         ["three", 3, "Here is yet another flag, 3."]],
                  default=[1, 3]),
    fm.Choice("arg4",
              choices=[[str(n), n, "The number %s." % n] for n in xrange(100)],
              default=7),
    fm.Text("arg5", "HERE IS THE DEFAULT OMG!@#!.",
            "TEXT PLS", "it is some text")
    )

def proc(**kw):
    print kw


class FormPage(Page):

    template = '''
    <html>
    <head><title>a form page</title>
    </head>
    <body>
    <form action="post" model="form" />
    </body>
    </html>
    '''

    def __init__(self):
        Page.__init__(self)
        self._form = formTestSignature.method(proc)

    def wmfactory_form(self, request):
        return self._form

    def wchild_post(self, request):
        return FormProcessor(self._form)

