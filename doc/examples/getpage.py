if __name__ == '__main__':
    from twisted.internet import reactor
    from twisted.web.client import getPage
    import sys
    d = getPage(sys.argv[1])
    def printValue(value):
        print value
        reactor.stop()
    def printError(error):
        print "an error occured", error
        reactor.stop()
    d.addCallbacks(callback=printValue, errback=printError)
    reactor.run()
