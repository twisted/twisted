from twisted.web import google
from twisted.internet import reactor 
import sys

def printValue(location):
     print location
     reactor.stop()

def printError(error):
     print 'error', error
     reactor.stop()

google.checkGoogle(sys.argv[1:]).addCallbacks(printValue, printError)
reactor.run()
