
from twisted.internet.app import Application
from twisted.web.server import Site
from macrodemo import MacroDemo, NothingModel
application = a = Application("demo")

a.listenTCP(8182,Site(MacroDemo(NothingModel())))
