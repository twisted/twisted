from twisted.web.woven import page, view, widgets
from twisted.web.microdom import lmx
from twisted.internet import defer

class Thingie:
    pass

class ThingWidget(widgets.Widget):
    def setUp(self, request, node, data):
        l = lmx(node)
        l.text('foo')

    def generate(self, request, node):
        print 'GENERATE', [request, node]
        data = self.getData(request)
        if isinstance(data, defer.Deferred):
            data.addCallback(self.setDataCallback, request, node)
            data.addErrback(utils.renderFailure, request)
            return data
        return self._regenerate(request, node, data)

view.registerViewForModel(ThingWidget, Thingie)

class Broken(page.Page):
    """This fails with a Deferred model if you remove the middle model=. level.
    fzZzy said it's DeferredWidget's fault."""

    template = '''\
<?xml version="1.0" encoding="UTF-8"?>
<html>
<div model="base" view="Widget">
<div model=".">
  <div model="dn" view="Text" />
  </div>
</div>
</html>
    '''

    def wmfactory_base(self, request):
        if True: # toggle me elmo!
            d=defer.Deferred()
            d.callback(Thingie())
            return d
        else:
            return Thingie()

class FakeRequest:
    uri='uri/'
    isSecure=lambda _: False
    def getHeader(self, name):
        pass
    def redirect(self, url):
        pass
    def write(self, data):
        print 'WRITE', repr(data)
    def finish(self):
        pass
    def setHeader(self, name, value):
        pass

print 'RETURN %r' % Broken().render(FakeRequest())
