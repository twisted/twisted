#!/usr/bin/python

from slides import Lecture, Slide, Image, Bullet, PRE, URL, SubBullet, NumSlide, toHTML
import os

class Bad:
    """Marks the text in red."""

    def __init__(self, text):
        self.text = text

    def toHTML(self):
        return '<font color="red">%s</font>' % toHTML(self.text)


class Lecture(Lecture):

    def getFooter(self):
        return '<div class="footer"><hr noshade />Presented by <b>ZOTECA&nbsp;</b></div>'


EVENT_LOOP_CODE = """\
# pseudo-code reactor
class Reactor:
    def run(self):
        while 1:
            e = self.getNextEvent()
            e.run()
"""

PROTOCOL_CODE = """\
from twisted.internet.protocol import Protocol

class Echo(Protocol):
    def connectionMade(self):
        print 'connection made with', self.transport.getPeer()
    def dataReceived(self, data):
        self.transport.write(data)
    def connectionLost(self, reason):
        print 'connection was lost, alas'
"""

SERVER_CODE = """\
from twisted.internet.protocol import ServerFactory

class EchoFactory(ServerFactory):

    def buildProtocol(self, addr):
        p = Echo()
        p.factory = self
        return p
"""

RUNNING_SERVER_CODE = """\
from twisted.internet import reactor

f = EchoFactory()
reactor.listenTCP(7771, f)
reactor.run()
"""

CLIENT_PROTOCOL_CODE = """\
from twisted.internet.protocol import Protocol

class MyClientProtocol(Protocol):
    buffer = ''
    def connectionMade(self):
        self.transport.write('hello world')
    def dataReceived(self, data):
        self.buffer += data
        if self.buffer == 'hello world':
            self.transport.loseConnection()
"""

CLIENT_FACTORY_CODE = """\
from twisted.internet.protocol import ClientFactory

class MyFactory(ClientFactory):

    protocol = MyClientProtocol

    def startedConnecting(self, connector):
        pass # we could connector.stopConnecting()
    def clientConnectionMade(self, connector):
        pass # we could connector.stopConnecting()
    def clientConnectionLost(self, connector, reason):
        connector.connect() # reconnect
    def clientConnectionFailed(self, connector, reason):
        print "connection failed"
        reactor.stop()
"""

CLIENT_CONNECT_CODE = """\
from twisted.internet import reactor

reactor.connectTCP('localhost', 7771, MyFactory(), timeout=30)
reactor.run()
"""

PULL_PRODUCER_CODE = """\
class FileProducer:

    def __init__(self, file, size, transport):
        self.file = file; self.size = size
        self.transport = transport # the consumer
        transport.registerProducer(self, 0)
    
    def resumeProducing(self):
        if not self.transport: return
        self.transport.write(self.file.read(16384))
        if self.file.tell() == self.size:
            self.transport.unregisterProducer()
            self.transport = None

    def pauseProducing(self): pass
    
    def stopProducing(self):
        self.file.close()
        self.request = None
"""

PUSH_PRODUCER_CODE = """\
from twisted.internet import reactor

class GarbageProducer:

    def __init__(self, transport):
        self.paused = 0; self.stopped = 0
        self.transport = transport
        transport.registerProducer(self, 1)
        self.produce()

    def produce(self):
        if not self.paused:
            self.transport.write('blabla')
        if not self.stopped:
            reactor.callLater(0.1, self.produce)

    def stopProducing(self):
        self.stopped = 1

    def pauseProducing(self):
        self.paused = 1

    def resumeProducing(self):
        self.paused = 0
"""

SCHEDULING_CODE = """\
from twisted.internet import reactor

def f(x, y=1):
    print x, y

i = reactor.callLater(0.1, f, 2, y=4)
i.delay(2)
i.reset(1)
i.cancel()
"""

FACTORY_START_CODE = """\
from twisted.internet.protocol import ServerFactory

class LogFactory(ServerFactory):

    def startFactory(self):
        self.log = open('log.txt', 'w')

    def stopFactory(self):
        self.log.close()
"""

LOGGING_CODE = """\
from twisted.python import log

# by default only errors are logged, to stderr
logFile = open('log.txt', 'a')
log.startLogging(logFile)

log.msg('Something has occurred')
"""

LOGGING_ERRORS_CODE = """
from twisted.python import log, failure

e = ValueError('ONO')
log.err(failure.Failure(e))

try:
    doSomethingElse()
except:
    log.deferr()
"""

SERVICE_CODE = """\
from twisted.internet import app

class FooService(app.ApplicationService):
    def startService(self):
        # do startup stuff
    def stopService(self):
        # do shutdown stuff
    def foobrizate(self):
        # business logic!

application = app.Application('foobnator')
svc = FooService('foo', application)
application.getServiceNamed('foo') is svc # True
"""

RUNNABLE_APP_CODE = """\
# this is web.py
from twisted.internet import app
from twisted.web import static, server

application = app.Application('web')
application.listenTCP(8080, server.Site(static.File('/var/www')))

if __name__ == '__main__':
    application.run(save=0)
"""

TWISTD_CODE = """\
$ twistd -y web.py
$ lynx http://localhost:8080
$ kill `cat twistd.pid`
"""

GUI_CODE = """\
from twisted.internet import gtkreactor
gtkreactor.install()
import gtk
w = gtk.GtkWindow(gtk.WINDOW_TOPLEVEL)
w.show_all()
from twisted.internet import reactor
reactor.run()
"""

lecture = Lecture(
    "The twisted.internet Tutorial of Doom",

    Slide("Part 1 - Introduction"),
    
    # there are different ways to do networking
    # mention processes are not cross-platform
    Slide("Choosing a networking paradigm for the enterprise",
          Bullet("Event driven"),
          Bullet(Bad("Threads")),
          Bullet("Others which we will ignore (processes, SEDA, ...)")),

    # it's a metaphor!
    Slide("Applied Bistromathics 101",
          Bullet("Consider a restaurant as a network application"),
          Bullet("Clients come in, make requests to the waiters"),
          Bullet("Waiters act on clients' choices")),

    # an event loop is efficient, doesn't waste time
    # event loop is also used for GUIs
    Slide("The event driven waiter",
          Bullet("One waiter, serving all tables"),
          Bullet("Waiter takes orders from tables to kitchen"),
          Bullet("Waiter takes food from kitchen to tables")),

    # not accurate, but the problems are real. avoid threads if you can
    Slide("Threads (a caricature)",
          Bullet(Bad("One waiter per table")),
          SubBullet("Problems:",
                    Bullet(Bad("Expensive")),
                    Bullet(Bad("Waiters need to be careful not bump into each other")),
                    )),

    # why threads are sometimes necessary
    Slide("When do we want threads?",
          Bullet("Long running, blocking operations"),
          Bullet("Classic example: database access")),

    # today we will discuss only (parts of) twisted.internet
    Slide("Twisted: The Framework of Your Internet",
          Image("twisted-overview.png")),

    Slide("Project Stats",
          Bullet("URL: ", URL("http://www.twistedmatrix.com")),
          Bullet("License: LGPL"),
          Bullet("Number of developers: approximately 20"),
          Bullet("Version: 1.0.3"), 
          Bullet("Platforms: Unix, Win32"),
          Bullet("Started in January 2000 by Glyph Lefkowitz")),

    Slide("Part 2 - Basic Networking With Twisted"),

    # quick review of how the internet works
    Slide("Internet!",
          Bullet("Network of interconnected machines"),
          Bullet("Each machine has one (or more) IP addresses"),
          Bullet("DNS maps names ('www.yahoo.com') to IPs (216.109.125.69)"),
          Bullet("TCP runs on top of IP, servers listen on of of 65536 ports,"
                 " e.g. HTTP on port 80"),),

    # we need to understand certain basic terms before we continue.
    # the event loop is the last thing we run - it waits until
    # an event occurs, then calls the appropriate handler.
    Slide("Basic Definitions - Reactor",
          Bullet("An object implementing the event loop",
                 PRE(EVENT_LOOP_CODE))),

    Slide("Basic Definitions - Transport",
          Bullet("Moves data from one location to another"),
          Bullet("Main focus of talk are ordered, reliable byte stream transports"),
          Bullet("Examples: TCP, SSL, Unix sockets"),
          Bullet("UDP is a different kind of transport")),

    # the client is the side which initiated the connection
    # HTTP and SSH run on TCP-like transports, DNS runs on UDP or TCP
    Slide("Basic Definitions - Protocol",
          Bullet("Defines the rules for communication between two hosts"),
          Bullet("Protocols communicate using a transport"),
          Bullet("Typically there is a client, and server"),
          Bullet("Examples: HTTP, SSH, DNS")),

    Slide("All Together Now",
          Bullet("The reactor gets events from the transports (read from network, write to network)"),
          Bullet("The reactor passes events to protocol (connection lost, data received)"),
          Bullet("The protocol tells the transport to do stuff (write data, lose connection)")),

    # designing a new protocol is usually a bad idea, there are lots of
    # things you can get wrong, both in design and in implementation
    Slide("How To Implement A Protocol",
          Bullet("Hopefully, you don't.")),

    # XXX split into three expanded slides?
    NumSlide("How To Not Implement A Protocol",
             Bullet("Use an existing Twisted implementation of the protocol"),
             Bullet("Use XML-RPC"),
             Bullet("Use Perspective Broker, a remote object protocol")),

    # connectionMade is called when connection is made
    # dataReceived is called every time we receive data from the network
    # connectionLost is called when the connection is lost
    Slide("How To Really Implement A Protocol",
          PRE(PROTOCOL_CODE)),
    
    # factories - why?
    Slide("Factories",
          Bullet("A protocol instance only exists as long as the connection is there"),
          Bullet("Protocols want to share state"),
          Bullet("Solution: a factory object that creates protocol instances")),
    
    # factory code - notice how protocol instances have access to the factory
    # instance, for shared state. buildProtocol can return None if we don't
    # want to accept connections from that address.
    Slide("A Server Factory",
          PRE(SERVER_CODE)),
    
    # running the server we just wrote
    Slide("Connecting A Factory To A TCP Port",
          PRE(RUNNING_SERVER_CODE)),
    
    # transport independence - using listenUNIX as example
    Slide("Transport Independence",
          Bullet("Notice how none of the protocol code was TCP specific"),
          Bullet("We can reuse same protocol with different transports"),
          Bullet("We could use listenUNIX for unix sockets with same code"),
          Bullet("Likewise listenSSL for SSL or TLS")),

    Slide("Client Side Protocol",
          PRE(CLIENT_PROTOCOL_CODE)),
    
    # client connections are different
    Slide("Client Side Factories",
          Bullet("Different requirements than server"),
          Bullet("Failure to connect"),
          Bullet("Automatic reconnecting"),
          Bullet("Cancelling and timing out connections")),
    
    # example client factory - explain use of default buildProtocol
    Slide("Client Side Factories 2",
          PRE(CLIENT_FACTORY_CODE)),
    
    # connectTCP
    Slide("Connection API",
          PRE(CLIENT_CONNECT_CODE)),

    # explain how transports buffer the output
    Slide("Buffering",
          Bullet("When we write to transport, data is buffered"),
          Bullet("loseConnection will wait until all buffered data is sent, and producer (if any) is finished")),
    
    # start/stopFactory
    Slide("Factory Resources",
          Bullet("Factories may want to create/clean up resources"),
          Bullet("startFactory() - called on start of listening/connect"),
          Bullet("stopFactory() - called on end of listening/connect"),
          Bullet("Called once even if factory listening/connecting multiple ports")),
    
    # example of restartable factory
    Slide("Factory Resources 2",
          PRE(FACTORY_START_CODE)),
    
    Slide("Producers and Consumers",
          Bullet("What if we want to send out lots of data?"),
          Bullet("Can't write it out all at once"),
          Bullet("We don't want to write too fast")),

    Slide("Producers",
          Bullet("Produce data for a consumer, in this case by calling transport's write()"),
          Bullet("Pausable (should implement pauseProducing and resumeProducing methods)"),
          Bullet("Push - keeps producing unless told to pause"),
          Bullet("Pull - produces only when consumer tells it to")),

    Slide("Consumers",
          Bullet("registerProducer(producer, streaming)"),
          Bullet("Will notify producer to pause if buffers are full")),

    Slide("Sample Pull Producer",
          PRE(PULL_PRODUCER_CODE)),

    Slide("Sample Push Producer",
          PRE(PUSH_PRODUCER_CODE)),

    # scheduling events
    Slide("Scheduling",
          PRE(SCHEDULING_CODE)),

    # pluggable reactors - why?
    Slide("Choosing a Reactor - Why?",
          Bullet("GUI toolkits have their own event loop"),
          Bullet("Platform specific event loops")),

    Slide("Choosing a Reactor",
          Bullet("Twisted supports multiple reactors"),
          Bullet("Default, gtk, gtk2, qt, win32 and others"),
          Bullet("Tk and wxPython as non-reactors"),
          Bullet("Reactor installation should be first thing code does")),
          
    # example GUI client
    Slide("Example GTK Program",
          PRE(GUI_CODE)),
    
    # you can learn more about
    Slide("Learning more about networking and scheduling",
          Bullet("twisted.internet.interfaces"),
          Bullet("http://twistedmatrix.com/document/howtos/")),
    

    Slide("Part 3 - Building Applications With Twisted"),
    
    # the concept of the application
    Slide("Applications",
          Bullet("Reactor is a concept of event loop"),
          Bullet("Application is higher-level"),
          Bullet("Configuration, services, persistence"),
          Bullet("Like reactor, you can listenTCP, connectTCP, etc.")),
    
    # services concept
    Slide("Services",
          Bullet("Services can be registered with Application"),
          Bullet("A service encapsulates 'business logic'"),
          Bullet("Infrastructure outside the scope of protocols"),
          Bullet("Examples: authentication, mail storage")),
    
    # service example code
    Slide("Services 2",
          PRE(SERVICE_CODE)),
    
    # logging
    Slide("Logging",
          PRE(LOGGING_CODE)),
    
    # logging errors
    # explain why this is good idea (twistd -b)
    Slide("Logging Errors",
          PRE(LOGGING_ERRORS_CODE)),
    
    # twistd idea
    Slide("twistd - Application Runner",
          Bullet("Single access point for running applications"),
          Bullet("Separate configuration from deployment")),
    
    # twistd features
    Slide("twistd Features",
          Bullet("Daemonization"),
          Bullet("Log file selection (including to syslog)"),
          Bullet("Choosing reactor"),
          Bullet("Running under debugger"),
          Bullet("Profiling"),
          Bullet("uid, gid"),
          Bullet("Future: WinNT Services")),
    
    # making modules for twistd -y
    Slide("Making a runnable application",
          PRE(RUNNABLE_APP_CODE)),

    # running the server
    Slide("Running twistd",
          PRE(TWISTD_CODE)),

    Slide("Part 4: Further Bits and Pieces"),

    Slide("Other twisted.internet Features",
          Bullet("UDP, Multicast, Unix sockets, Serial"),
          Bullet("Thread integration")),
          
    Slide("Deferreds",
          Bullet("Deferred - a promise of a result"),
          Bullet("Supports callback chains for results and exceptions"),
          Bullet("Used across the whole framework"),
          Bullet("Make event-driven programming much easier"),
          Bullet("Can work with asyncore too, not just Twisted")),

    Slide("Protocol implementations",
          Bullet("Low-level implementations, without policies"),
          Bullet("SSH, HTTP, SMTP, IRC, POP3, telnet, FTP, TOC, OSCAR, SOCKSv4, finger, DNS, NNTP, IMAP, LDAP"),
          Bullet("Common GPS modem protocols")),

    Slide("Frameworks",
          Bullet("twisted.web - Web server framework"),
          Bullet("twisted.news - NNTP server framework"),
          Bullet("twisted.words - messaging framework"),
          Bullet("twisted.names - DNS server")),

    Slide("Perspective Broker",
          Bullet("Object publishing protocol"),
          Bullet("Fast, efficient and extendable"),
          Bullet("Two-way, asynchronous"),
          Bullet("Secure and encourages secure model"),
          Bullet("Implemented in Python for Twisted, and Java")),

    Slide("Lore",
          Bullet("Simple documentation system"),
          Bullet("Simple subset of XHTML"),
          Bullet("Generates LaTeX, XHTML")),

    Slide("Reality",
          Bullet("Multiplayer text simulation framework"),
          Bullet("Original source of Twisted project"),
          Bullet("Now a totally different project")),
)


if __name__ == '__main__':
    lecture.renderHTML(".", "twisted_internet-%02d.html", css="main.css")
