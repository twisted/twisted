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
proxy.callMethod('defer').addCallbacks(printValue, printError)
reactor.run()
proxy.callMethod('fail').addCallbacks(printValue, printError)
reactor.run()
proxy = Proxy('http://advogato.org/XMLRPC')
proxy.callMethod('test.sumprod', 3, 5).addCallbacks(printValue, printError)
reactor.run()
