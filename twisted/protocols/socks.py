#sibling imports
import protocol
from twisted.internet import tcp

#python imports
import struct
import string
import socket

class SOCKSv4Outgoing(protocol.Protocol):
    def __init__(self,socks):
        self.socks=socks
    def connectionMade(self):
        self.socks.makeReply(90)
        self.socks.otherConn=self
    def connectionFailed(self):
        self.socks.makeReply(91)
    def connectionLost(self):
        self.socks.transport.loseConnection()
    def dataReceived(self,data):
        self.socks.write(data)
    def write(self,data):
        self.socks.log(self,data)
        self.transport.write(data)

class SOCKSv4Incoming(protocol.Protocol):
    def __init__(self,socks):
        self.socks=socks
        self.socks.otherConn=self
    def connectionLost(self):
        self.socks.transport.loseConnection()
    def dataReceived(self,data):
        self.socks.write(data)
    def write(self,data):
        self.socks.log(self,data)
        self.transport.write(data)

class SOCKSv4(protocol.Protocol):
    def __init__(self,logging=None):
        self.logging=logging
    def connectionMade(self):
        self.buf=""
        self.otherConn=None

    def dataReceived(self,data):
        if self.otherConn:
            self.otherConn.write(data)
            return
        self.buf=self.buf+data
        if '\000' in self.buf[8:]:
            #print repr(self.buf)
            head,self.buf=self.buf[:8],self.buf[8:]
            try:
                version,code,port=struct.unpack("!BBH",head[:4])
            except struct.error:
                assert 0,"struct error with head='%s' and buf='%s'"%(repr(head),repr(self.buf))
            user,self.buf=string.split(self.buf,"\000",1)
            if head[4:7]=="\000\000\000": # domain is after
                server,self.buf=string.split(self.buf,'\000',1)
                #server=gethostbyname(server)
            else:
                server=socket.inet_ntoa(head[4:8])
            assert version==4, "Bad version code: %s"%version
            if not self.authorize(code,server,port,user):
                self.makeReply(91)
                return
            if code==1: # CONNECT
                tcp.Client(server,port,SOCKSv4Outgoing(self))
            elif code==2: # BIND
                self.serv=tcp.Port(0,SOCKSv4IncomingFactory(self))
                self.serv.startListening()
                self.serv.approveConnection=self._approveConnection
                self.ip=socket.gethostbyname(server)
                ourip,ourport=self.serv.socket.getsockname()
                self.makeReply(90,0,ourport,ourip)
            else:
                assert 0, "Bad Connect Code: %s" % code
            assert self.buf=="","hmm, still stuff in buffer... '%s'"

    def authorize(self,code,server,port,user):
        print "code %s connection to %s:%s (user %s)"%(code,server,port,user)
        return 1

    def makeReply(self,reply,version=4,port=0,ip="0.0.0.0"):
        self.transport.write(struct.pack("!BBH",version,reply,port)+socket.inet_aton(ip))
        if reply!=90: self.transport.loseConnection()

    def write(self,data):
        self.log(self,data)
        self.transport.write(data)

    def log(self,proto,data):
        if not self.logging: return
        foo,host,port=proto.transport.getPeer()
        f=open(self.logging,"a")
        f.write("%s\t%s:%s\n"%((proto==self and '>' or '<'),host,port))
        while data:
            p,data=data[:16],data[16:]
            f.write(string.join(map(lambda x:'%02X'%ord(x),p),' ')+' ')
            for c in p:
                if len(repr(c))>3: f.write('.')
                else: out=f.write(c)
            f.write('\n')
        f.close()

    def _approveConnection(self,skt,addr):
        if addr[0]==self.ip:
            self.ip=""
            self.makeReply(90,0)
            return 1
        elif self.ip=="":
            return 0
        else:
            self.makeReply(91,0)
            self.ip=""
            return 0

class SOCKSv4Factory(protocol.Factory):
    def __init__(self,log):
        self.logging=log
    def buildProtocol(self,addr):
        return SOCKSv4(self.logging)

class SOCKSv4IncomingFactory(protocol.Factory):
    def __init__(self,socks):
        self.socks=socks
    def buildProtocol(self,addr):
        return SOCKSv4Incoming(self.socks)