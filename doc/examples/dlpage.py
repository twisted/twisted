if __name__ == '__main__':
    from twisted.internet import reactor
    from twisted.web.client import downloadPage
    import sys
    d = downloadPage(sys.argv[1], "foo")
    def printValue(value):
        print "done"
        reactor.stop()
    def printError(error):
        print "an error occured", error
        reactor.stop()
    d.addCallbacks(callback=printValue, errback=printError)
    reactor.run()
