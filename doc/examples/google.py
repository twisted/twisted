from twisted.web import google
from twisted.internet import reactor 

import sys
def printValue(location):
     print location
     reactor.stop()
def printError(error):
     print 'error', error
     reactor.stop()
d = google.checkGoogle(sys.argv[1:])
d.addCallbacks(printValue, printError)
reactor.run()
