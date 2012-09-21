

from zope.interface import Interface, implements

from ampserver import Math

from twisted.tubes.protocol import ProtocolAdapterCreatorThing as ThinkOfAName
from twisted.internet.endpoints import serverFromString

from twisted.internet import reactor

from twisted.protocols.amp import AmpBox
from twisted.protocols.amp import IBoxSender
from twisted.tubes.itube import ISegment
from twisted.tubes.tube import Valve
from twisted.tubes.tube import Tube
from twisted.protocols.basic import Int16StringReceiver


class IString(Interface):
    """
    A string that's a discrete message.
    """


class DataToStrings(Int16StringReceiver, Valve):

    inputType = ISegment
    outputType = IString

    def stringReceived(self, string):
        self.tube.deliver(string)


    def received(self, item):
        self.dataReceived(item)



class StringsToBoxes(Valve):

    inputType = IString
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



class BoxesToData(Valve):
    """
    Shortcut: I want to go from boxes directly to data.
    """
    inputType = None # AmpBox
    outputType = ISegment

    def received(self, item):
        self.tube.deliver(item.serialize())



class BoxConsumer(Valve):

    implements(IBoxSender)

    inputType = None # AmpBox
    outputType = None # AmpBox

    def __init__(self, boxReceiver):
        self.boxReceiver = boxReceiver


    def started(self):
        self.boxReceiver.startReceivingBoxes(self)


    def sendBox(self, box):
        self.tube.deliver(box)


    def unhandledError(self, failure):
        pass


    def received(self, box):
        self.boxReceiver.ampBoxReceived(box)



def boot(fount, drain):
    (fount.flowTo(Tube(DataToStrings()))
          .flowTo(Tube(StringsToBoxes()))
          .flowTo(Tube(BoxConsumer(Math())))
          .flowTo(Tube(BoxesToData()))
          .flowTo(drain))

serverEndpoint = serverFromString(reactor, "tcp:1234")
serverEndpoint.listen(ThinkOfAName(boot))
from twisted.internet import reactor
reactor.run()

