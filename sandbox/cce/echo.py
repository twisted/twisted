from __future__ import generators
from twisted.flow import flow
from twisted.internet import protocol, reactor
PORT = 8392

print "client                   server"
print "-------------------      ---------------------"
def echoServer(conn):
    print "                         connected, now wait for client"
    yield conn
    print "                         client responded"
    for data in conn:
        print "                         received '%s', sending back" % data 
        conn.write(data)
        print "                         waiting for client again"
        yield conn                                   
    print "                         disconnected"

server = protocol.ServerFactory()
server.protocol = flow.makeProtocol(echoServer)
reactor.listenTCP(PORT,server)

def echoClient(conn):
    print "connect and send"
    conn.write("Hello World")
    print "waiting for server"
    yield conn
    print "received '%s'" % conn.next()
    print "sending more"
    conn.write("Another Line")
    print "waiting for server"
    yield conn
    print "received '%s'" % conn.next()
    reactor.callLater(0,reactor.stop)
    print "disconnecting"

client = protocol.ClientFactory()
client.protocol = flow.makeProtocol(echoClient)
reactor.connectTCP("localhost", PORT, client)
reactor.run()
