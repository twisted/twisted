from twisted.spread import pb
from twisted.internet import tcp, main

def success(message):
    print "Message received:",message
    main.shutDown()

def failure(error):
    print "Failure..."
    main.shutDown()

def disconnected():
    print "disconnected."
    main.shutDown()

def connected(perspective):
    perspective.echo("hello world",
                     pbcallback=success,
                     pberrback=failure)
    
    print "connected."

def couldntConnect():
    print "Could not connect."
    main.shutDown()

# run a client
b = pb.Broker()
b.requestPerspective("pbecho", # service name
                     "guest",  # username
                     "guest",  # password
                     callback = connected,
                     errback  = couldntConnect)

tcp.Client("localhost",pb.portno,b)

main.run()
