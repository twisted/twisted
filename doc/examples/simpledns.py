from twisted.names import dns
from twisted.internet import main
from twisted.python import defer

deferred = defer.Deferred()

def printAnswer(answer):
    print answer
    main.shutDown()

def printFailure(arg):
    print "error: could not resolve", arg
    main.shutDown()

deferred.addCallback(printAnswer)
deferred.addErrback(printFailure)
deferred.arm()

resolver = dns.Resolver(["192.114.42.86"])
resolver.resolve(deferred, "www.zoteca.com")
main.run()
