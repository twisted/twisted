from twisted.names import dns
from twisted.internet import main

def printAnswer(answer):
    print answer
    main.shutDown()

def printFailure():
    print "error: could not resolve"
    main.shutDown()

resolver = dns.Resolver(["212.29.241.226"])
resolver.resolve("moshez.org", printAnswer, printFailure)
main.run()
