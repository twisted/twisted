from twisted.names import dns
from twisted.internet import main

def printAnswer(answer):
    print answer
    main.shutDown()

def printFailure(arg):
    print "error: could not resolve", arg
    main.shutDown()


resolver = dns.Resolver(["192.114.42.86"])
deferred = resolver.resolve("www.zoteca.com")
deferred.addCallback(printAnswer)
deferred.addErrback(printFailure)
deferred

main.run()
