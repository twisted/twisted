from myformstuf import FormPage
from twisted.internet.app import Application
from twisted.web.server import Site
application = Application('form')
application.listenTCP(8487, Site(FormPage()))
                      
