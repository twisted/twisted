from twisted.internet import utils, reactor

def printTrueValue(val):
    print val
    output = utils.getProcessValue('false')
    output.addCallback(printFalseValue)

def printFalseValue(val):
    print val
    reactor.stop()

output = utils.getProcessValue('true')
output.addCallback(printTrueValue)
reactor.run()
