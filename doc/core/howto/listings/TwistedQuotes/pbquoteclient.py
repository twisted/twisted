
from sys import stdout
from twisted.python import log
log.discardLogs()
from twisted.internet import reactor
from twisted.spread import pb

def connected(root):
    root.callRemote('nextQuote').addCallbacks(success, failure)

def success(quote):
    stdout.write(quote + "\n")
    reactor.stop()

def failure(error):
    stdout.write("Failed to obtain quote.\n")
    reactor.stop()

factory = pb.PBClientFactory()
reactor.connectTCP(
    "localhost", # host name
    pb.portno, # port number
    factory, # factory
    )



factory.getRootObject().addCallbacks(connected, # when we get the root
                                     failure)   # when we can't

reactor.run() # start the main loop

