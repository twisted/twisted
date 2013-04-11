# -*- test-case-name: twisted.tubes.test.test_framing -*-
"""
Protocols to support framing.
"""

from io import BytesIO
from twisted.tubes.tube import Pump
from twisted.protocols.basic import NetstringReceiver


class StringsToData(Pump):
    def __init__(self, stringReceiverClass):
        self._stringReceiver = stringReceiverClass()
        self._bytes = BytesIO()
        self._stringReceiver.makeConnection(self._bytes)


    def received(self, string):
        self._stringReceiver.sendString(string)
        self.tube.deliver(self._bytes.getvalue())
        self._bytes.seek(0)
        self._bytes.truncate(0)



class DataToStrings(Pump):
    def __init__(self, stringReceiverClass):
        self._stringReceiver = stringReceiverClass()
        self.received = self._stringReceiver.stringReceived


def stringsToNetstrings():
    return StringsToData(NetstringReceiver)


def netstringsToStrings():
    return DataToStrings(NetstringReceiver)
