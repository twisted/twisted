from twisted.web.xmlrpc import query
from twisted.internet import reactor

def printValue(value):
    print repr(value)
    reactor.stop()

def printError(error):
    print 'error', error
    reactor.stop()

query('localhost', 10999, '/', 'echo', 41).addCallbacks(printValue, printError)
reactor.run()
query('localhost', 10999, '/', 'defer').addCallbacks(printValue, printError)
reactor.run()
query('localhost', 10999, '/', 'fail').addCallbacks(printValue, printError)
reactor.run()
