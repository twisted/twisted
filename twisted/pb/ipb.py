

from zope.interface import interface
Interface = interface.Interface

# TODO: move these here
from twisted.pb.tokens import ISlicer, IRootSlicer, IUnslicer


class DeadReferenceError(Exception):
    """The RemoteReference is dead, Jim."""


class IReferenceable(Interface):
    """This object is remotely referenceable. This means it is represented to
    remote systems as an opaque identifier, and that round-trips preserve
    identity.
    """

    def processUniqueID():
        """Return a unique identifier (scoped to the process containing the
        Referenceable). Most objects can just use C{id(self)}, but objects
        which should be indistinguishable to a remote system may want
        multiple objects to map to the same PUID."""

class IRemotelyCallable(Interface):
    """This object is remotely callable. This means it defines some remote_*
    methods and may have a schema which describes how those methods may be
    invoked.
    """

    def getInterfaceNames():
        """Return a list of RemoteInterface names to which this object knows
        how to respond."""

    def doRemoteCall(methodname, kwargs):
        """Invoke the given remote method. This method may raise an
        exception, return normally, or return a Deferred."""

