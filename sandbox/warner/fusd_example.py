#! /usr/bin/python

from twisted.internet import reactor
import errno, sys
from twisted.spread import pb


def example_relay():
    from fusd_twisted import Device, OpenFile
    class RelayFile(OpenFile):
        """This class sends reads and writes over PB to a remote process."""
        def reqFailed(self, reason, req):
            req.finish(-errno.EIO)

        def do_read(self, req):
            print "do_read(%d)" % req.length
            d = self.device.peer.callRemote("read", req.length, req.offset)
            d.addCallback(self.read_complete, req)
            d.addErrback(self.reqFailed, req)
        def read_complete(self, data, req):
            assert (len(data) <= req.length)
            req.offset += len(data)
            req.setdata(0, data)
            req.finish(len(data))

        def do_write(self, req):
            print "do_write(%d)" % req.length
            data = req.getdata()
            d = self.device.peer.callRemote("write",
                                            req.length, req.offset, data)
            d.addCallback(self.write_complete, req)
            d.addErrback(self.reqFailed, req)
        def write_complete(self, rc, req):
            req.offset += rc
            req.finish(rc)
            
    d = Device(RelayFile, "/dev/twisted", 0666)
    def gotObject(object, d=d):
        print "connected to server"
        d.peer = object
    def noObject(reason):
        print "couldn't connect to server"
        print reason
        reactor.stop()
    pb.getObjectAt("localhost", 8999, 5).addCallbacks(gotObject, noObject)
    reactor.run()


def example_server():
    class Echoer(pb.Root):
        buffer = ""
        def remote_read(self, length, offset):
            print "remote_read(%d)" % length
            data = self.buffer[:length]
            self.buffer = self.buffer[length:]
            return data
        def remote_write(self, length, offset, data):
            print "remote_write(%d)" % length
            self.buffer += data
            return length
    reactor.listenTCP(8999, pb.BrokerFactory(Echoer()))
    print "server is now waiting for connections"
    reactor.run()

usage = """
1: Install the kfusd kernel module.
2: Start the server:
     ./fusd_example.py --server
3: Start the relay:
     PYTHONPATH=.../fusd/python/build/lib.arch-pver ./fusd_example.py --relay
4: Put data into the buffer:
     echo 'howdy' >/dev/twisted
   Both the relay and the server should mention that something has been written
5: Read data out of the buffer:
     cat /dev/twisted
   Both the relay and the server should mention that something is being read
"""

if len(sys.argv) < 2 or sys.argv[1] not in ("--server", "--relay"):
    print usage
elif sys.argv[1] == "--server":
    example_server()
elif sys.argv[1] == "--relay":
    example_relay()
else:
    print usage
