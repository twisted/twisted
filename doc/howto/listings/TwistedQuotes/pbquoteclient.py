
from sys import stdout
from twisted.python import log
log.discardLogs()
from twisted.internet import reactor
from twisted.spread import pb

def connected(perspective):
    perspective.callRemote('nextQuote').addCallbacks(success, failure)

def success(quote):
    stdout.write(quote + "\n")
    reactor.stop()

def failure(error):
    stdout.write("Failed to obtain quote.\n")
    reactor.stop()

pb.connect("localhost", # host name
           pb.portno, # port number
           "guest", # identity name
           "guest", # password
           "twisted.quotes", # service name
           "guest", # perspective name (usually same as identity)
           30 # timeout of 30 seconds before connection gives up
           ).addCallbacks(connected, # what to do when we get connected
                          failure) # and what to do when we can't

reactor.run() # start the main loop

