

from zope.interface import implementer

from ampserver import Math

from twisted.tubes.protocol import factoryFromFlow
from twisted.internet.endpoints import serverFromString

from twisted.internet import reactor

from twisted.protocols.amp import AmpBox, IBoxSender
from twisted.tubes.itube import ISegment
from twisted.tubes.tube import Pump, series
from twisted.tubes.framing import packedPrefixToStrings

class StringsToBoxes(Pump):

    inputType = None # I... Packet? IString? IDatagram?
    outputType = None # AmpBox -> TODO, implement classes.

    state = 'new'

    def received(self, item):
        self.state = getattr(self, 'received_' + self.state)(item)


    def received_new(self, item):
        self._currentBox = AmpBox()
        return self.received_key(item)


    def received_key(self, item):
        if item:
            self._currentKey = item
            return 'value'
        else:
            self.tube.deliver(self._currentBox)
            return 'new'


    def received_value(self, item):
        self._currentBox[self._currentKey] = item
        return 'key'



class BoxesToData(Pump):
    """
    Shortcut: I want to go from boxes directly to data.
    """
    inputType = None # AmpBox
    outputType = ISegment

    def received(self, item):
        self.tube.deliver(item.serialize())



@implementer(IBoxSender)
class BoxConsumer(Pump):

    inputType = None # AmpBox
    outputType = None # AmpBox

    def __init__(self, boxReceiver):
        self.boxReceiver = boxReceiver


    def started(self):
        self.boxReceiver.startReceivingBoxes(self)


    def sendBox(self, box):
        self.tube.deliver(box)


    def unhandledError(self, failure):
        failure.printTraceback()


    def received(self, box):
        self.boxReceiver.ampBoxReceived(box)



def mathFlow(fount, drain):
    fount.flowTo(series(packedPrefixToStrings(16), StringsToBoxes(),
                         BoxConsumer(Math()), BoxesToData(), drain))



serverEndpoint = serverFromString(reactor, "tcp:1234")
serverEndpoint.listen(factoryFromFlow(mathFlow))
from twisted.internet import reactor
reactor.run()

