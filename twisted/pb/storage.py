
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

from twisted.pb import slicer, banana

class UnsafeRootUnslicer(slicer.RootUnslicer):
    topRegistry = [slicer.UnslicerRegistry, slicer.UnsafeUnslicerRegistry]
    openRegistry = [slicer.UnslicerRegistry, slicer.UnsafeUnslicerRegistry]

class StorageRootUnslicer(UnsafeRootUnslicer, slicer.ScopedUnslicer):
    # This version tracks references for the entire lifetime of the
    # protocol. It is most appropriate for single-use purposes, such as a
    # replacement for Pickle.

    def __init__(self):
        slicer.ScopedUnslicer.__init__(self)
        UnsafeRootUnslicer.__init__(self)
    
    def setObject(self, counter, obj):
        return slicer.ScopedUnslicer.setObject(self, counter, obj)
    def getObject(self, counter):
        return slicer.ScopedUnslicer.getObject(self, counter)

class UnsafeRootSlicer(slicer.RootSlicer):
    slicerTable = slicer.UnsafeSlicerTable

class StorageRootSlicer(UnsafeRootSlicer):
    # some pieces taken from ScopedSlicer
    def __init__(self, protocol):
        UnsafeRootSlicer.__init__(self, protocol)
        self.references = {}

    def registerReference(self, refid, obj):
        self.references[id(obj)] = (obj,refid)

    def slicerForObject(self, obj):
        # check for an object which was sent previously or has at least
        # started sending
        obj_refid = self.references.get(id(obj), None)
        if obj_refid is not None:
            return slicer.ReferenceSlicer(obj_refid[1])
        # otherwise go upstream
        return UnsafeRootSlicer.slicerForObject(self, obj)

class StorageBanana(banana.Banana):
    # this is "unsafe", in that it will do import() and create instances of
    # arbitrary classes. It is also scoped at the root, so each
    # StorageBanana should be used only once.
    slicerClass = StorageRootSlicer
    unslicerClass = StorageRootUnslicer

    # it also stashes top-level objects in .obj, so you can retrieve them
    # later
    def receivedObject(self, obj):
        self.object = obj

def serialize(obj):
    """Serialize an object graph into a sequence of bytes. Returns a Deferred
    that fires with the sequence of bytes."""
    b = StorageBanana()
    b.transport = StringIO.StringIO()
    d = b.send(obj)
    d.addCallback(lambda res: b.transport.getvalue())
    return d

def unserialize(str):
    """Unserialize a sequence of bytes back into an object graph."""
    b = StorageBanana()
    b.dataReceived(str)
    return b.object

