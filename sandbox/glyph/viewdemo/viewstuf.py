
from twisted.web.woven import model, view, page, interfaces

class V(view.View):
    template = '''
    <div class="good">
    It is a totally awesome view!
    <span class="good" model="s">THIS TEXT SHOULD GO AWAY</span>
    </div>
    '''

class Va(view.View):
    template = '''
    <div class="good">
    This is an adapter-magical view!

    <span class="good" model="q">
    </span>
    </div>
    '''

class Ma(model.AttributeModel):
    q = "And this is a string gotten from an adapter-magic model."

class A:
    pass

from twisted.python.components import registerAdapter
view.registerViewForModel(Va, Ma)
registerAdapter(Ma, A, interfaces.IModel)

class P(page.Page):
    template = '''
    <html>
    <head><title>P</title>

    <style>
    div.good { border: thin solid blue; margin: 3px; padding: 3px; }
    span.good { background-color: #ccf; border: thin solid green; margin: 1px; padding: 1px; }
    .bad { border: thick dashed red }
    </style>
    </head>
    
    <body>

    Demo of both model and view specified:
    
    <div class="bad" view="v" model="m">
    THIS TEXT IS INVISIBLE
    </div>

    Demo of a model which gets its view through adapter magic:

    <div class="bad" model="a">

    </div>
    
    </body>
    </html>
    '''

    def wmfactory_m(self, request):
        m = model.AttributeModel()
        m.s = 'it is a string'
        return m

    def wvfactory_v(self, request, node, model):
        return V(model)

    def wmfactory_a(self):
        return A()
