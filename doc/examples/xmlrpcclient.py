from twisted.web.xmlrpc import Proxy
from twisted.internet import reactor

def printValue(value):
    print repr(value)
    reactor.stop()

def printError(error):
    print 'error', error
    reactor.stop()

proxy = Proxy('http://advogato.org/XMLRPC')
proxy.callMethod('test.sumprod', 3, 5).addCallbacks(printValue, printError)
reactor.run()
proxy.callMethod('test.capitalize', 'moshe zadka').addCallbacks(printValue,
                                                                printError)
reactor.run()
proxy = Proxy('http://time.xmlrpc.com/RPC2')
proxy.callMethod('currentTime.getCurrentTime').addCallbacks(printValue, printError)
reactor.run()
proxy = Proxy('http://betty.userland.com/RPC2')
proxy.callMethod('examples.getStateName', 41).addCallbacks(printValue, printError)
reactor.run()
