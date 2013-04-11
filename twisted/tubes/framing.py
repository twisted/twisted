# -*- test-case-name: twisted.tubes.test.test_framing -*-
"""
Protocols to support framing.
"""

from twisted.tubes.tube import Pump
from twisted.protocols.basic import NetstringReceiver

class _Transporter(object):
    def __init__(self, pump):
        self.pump = pump


    def write(self, data):
        self.pump.tube.deliver(data)



class StringsToData(Pump):
    def __init__(self, stringReceiverClass):
        self._stringReceiver = stringReceiverClass()
        self._stringReceiver.makeConnection(_Transporter(self))


    def received(self, string):
        self._stringReceiver.sendString(string)



class DataToStrings(Pump):
    def __init__(self, stringReceiverClass):
        self._stringReceiver = stringReceiverClass()
        self._stringReceiver.makeConnection(None)


    def started(self):
        self._stringReceiver.stringReceived = self.tube.deliver


    def received(self, string):
        self._stringReceiver.dataReceived(string)



def stringsToNetstrings():
    return StringsToData(NetstringReceiver)



def netstringsToStrings():
    return DataToStrings(NetstringReceiver)
