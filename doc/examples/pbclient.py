from twisted.spread import pb
from twisted.internet import tcp, main

def success(message):
    print "Message received:",message
    main.shutDown()

def failure(error):
    print "Failure...",error
    main.shutDown()

def disconnected():
    print "disconnected."
    main.shutDown()

def connected(perspective):
    perspective.echo("hello world",
                     pbcallback=success,
                     pberrback=failure)
    
    print "connected."

def preConnected(identity):
    identity.attach("pbecho", None,
                    pbcallback=connected,
                    pberrback=failure)

def couldntConnect():
    print "Could not connect."
    main.shutDown()

# run a client
b = pb.Broker()
b.requestIdentity("guest",  # username
                  "guest",  # password
                  callback = preConnected,
                  errback  = couldntConnect)

tcp.Client("localhost",pb.portno,b)

main.run()
