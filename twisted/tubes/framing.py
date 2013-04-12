# -*- test-case-name: twisted.tubes.test.test_framing -*-
"""
Protocols to support framing.
"""

from twisted.tubes.tube import Pump
from twisted.protocols.basic import LineOnlyReceiver
from twisted.protocols.basic import NetstringReceiver

class _Transporter(object):
    def __init__(self, pump):
        self.pump = pump


    def write(self, data):
        self.pump.tube.deliver(data)


    def writeSequence(self, dati):
        for data in dati:
            self.write(data)



class _StringsToData(Pump):
    def __init__(self, stringReceiverClass, sendMethodName="sendString"):
        self._stringReceiver = stringReceiverClass()
        self._stringReceiver.makeConnection(_Transporter(self))
        self.received = getattr(self._stringReceiver, sendMethodName)



class _NotDisconnecting(object):
    """
    Enough of a transport to pretend to not be disconnecting.
    """
    disconnecting = False


class _DataToStrings(Pump):
    def __init__(self, stringReceiverClass,
                 receivedMethodName="stringReceived"):
        self._stringReceiver = stringReceiverClass()
        self._receivedMethodName = receivedMethodName
        self._stringReceiver.makeConnection(_NotDisconnecting())


    def started(self):
        setattr(self._stringReceiver, self._receivedMethodName,
                self.tube.deliver)


    def received(self, string):
        self._stringReceiver.dataReceived(string)



def stringsToNetstrings():
    return _StringsToData(NetstringReceiver)



def netstringsToStrings():
    return _DataToStrings(NetstringReceiver)



def linesToBytes():
    return _StringsToData(LineOnlyReceiver, "sendLine")



def bytesToLines():
    return _DataToStrings(LineOnlyReceiver, "lineReceived")

