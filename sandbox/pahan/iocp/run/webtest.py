import proactor
proactor.install()
from twisted.web import server, static
from twisted.internet import reactor
from twisted.python import log
import sys

log.startLogging(sys.stdout, setStdout = 0)

root = static.File(".")
site = server.Site(root)
reactor.listenTCP(8001, site)
reactor.run()

