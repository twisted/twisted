# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted's unit tests.
"""

__all__ = [
    'AccumulatingProtocol',
    'LineSendingProtocol',
    'FakeDatagramTransport',
    'StringTransport',
    'StringTransportWithDisconnection',
    'StringIOWithoutClosing',
    'MemoryReactor',
    'MemoryReactorClock',
    'RaisingMemoryReactor',
    'NonStreamingProducer',
    'waitUntilDisconnected',
    'EventLoggingObserver'
]

from twisted.python.deprecate import deprecatedModuleAttribute
from twisted.python.versions import Version

for i in __all__:
    deprecatedModuleAttribute(
        Version('Twisted', 'NEXT', 0, 0),
        'Please use twisted.internet.testing.{} instead.'.format(i),
        __name__,
        i)

