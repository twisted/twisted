from twisted.web.xmlrpc import Proxy
from twisted.internet import reactor

def printValue(value):
    print repr(value)
    reactor.stop()

def printError(error):
    print 'error', error
    reactor.stop()

proxy = Proxy('http://localhost:10999/')
proxy.callMethod('echo', 41).addCallbacks(printValue, printError)
reactor.run()
proxy.defer().addCallbacks(printValue, printError)
reactor.run()
proxy.fail().addCallbacks(printValue, printError)
reactor.run()
