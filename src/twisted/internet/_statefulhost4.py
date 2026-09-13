"""
as each address is resolved:

(convert it to an endpoint) if we are beneath the concurrent connection
threshold: connect to it on connection: abort any other outgoing connections
complete the deferred.  on error: remember the failure for later if resolution
has completed and all outgoing connections are done: complete the deferred with
a MultiFailure of remembered failures else: enqueue it

name resolution states:

    - not resolving yet

    - receiving names

    - done resolving

        - when resolutionComplete triggers receivingNames->doneResolving - we
          need to check whether the outgoing connection state is idle and fail
          the deferred if so

outgoing connection states:

    - idle

        - when connectionFailed input triggers someOutgoingConnections->idle -
          we need to check whether the name resolver is done resolving and fail
          the deferred if so

    - some outgoing connections

    - parallel limit reached

combined state machine?

- not resolving
- resolving <-> resolving + connecting
- failed <- connecting -> succeeded

"""

from dataclasses import dataclass
from typing import Protocol

from zope.interface import implementer

from automat import TypeMachineBuilder

from twisted.internet.interfaces import IAddress, IHostResolution, IResolutionReceiver


@implementer(IResolutionReceiver)
class RRProto(Protocol):
    def resolutionBegan(self, resolutionInProgress: IHostResolution) -> None:
        ...

    def addressResolved(self, address: IAddress) -> None:
        ...

    def resolutionComplete(self) -> None:
        ...


@dataclass
class ResoState:
    ...


resolutionBuilder = TypeMachineBuilder(RRProto, ResoState)


class CxnEvents(Protocol):
    ...


@dataclass
class CxnState:
    ...


cxnBuilder = TypeMachineBuilder(CxnEvents, CxnState)
