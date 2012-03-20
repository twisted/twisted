
import greenlet
import json
import traceback
import uuid

from twisted.internet import endpoints
from twisted.internet import error
from twisted.internet import protocol
from twisted.internet import reactor


class ActorSocket(object):
    def __init__(self, proto):
        self.proto = proto

    def send(self, msg):
        self.proto.transport.write(msg)

    def recv(self):
        return self.proto.actor.recv("dataReceived")


class ActorClientProtocol(protocol.Protocol):
    def __init__(self, addr, actor, fd):
        self.addr = addr.host + ':' + str(addr.port)
        self.actor = actor
        self.fd = fd

    def connectionMade(self):
        print "connectionMade", self.addr, self.actor
        self.actor.cast("connectionMade", [self.fd, True])

    def dataReceived(self, data):
        print "dataReceived", self.addr, self.actor
        self.actor.cast("dataReceived", data)

    def connectionLost(self, reason):
        print "connectionLost", self, "error =", reason.check(error.ConnectionLost) is not None
        self.actor.cast("connectionLost", reason.check(error.ConnectionLost) is not None)


class ActorClientFactory(protocol.Factory):
    def __init__(self, actor):
        self.actor = actor
        self.connecting = {}
        self.cur_fd = 1

    def buildProtocol(self, addr):
        act = ActorClientProtocol(addr, self.actor, self.cur_fd)
        self.connecting[self.cur_fd] = act
        self.cur_fd += 1
        return act


class Address(object):
    def __init__(self, actor):
        self.__actor = actor

    def revoke(self):
        self.__actor = None

    def cast(self, pat, msg):
        if self.__actor is None:
            return

        if self.__actor.mailbox is None:
            self.__actor = None
            return

        self.__actor.cast(pat, msg)


class Actor(object):
    def __init__(self, dis, func, args, kw):
        actor_client_factory = ActorClientFactory(self)

        self.id = id = uuid.uuid4()
        self.mailbox = {}
        self.caps = {}

        if func is None:
            func = type(self).run

        self.spawn = dis.spawn

        def cast(pat, msg):
            if pat == "connectionLost":
                dis.decref(self)
            if not isinstance(msg, Address):
                msg = json.dumps(msg)
            self.mailbox.setdefault(pat, []).append(msg)
            dis.ready_to_run.append(self)
            if not dis.looping:
                dis.loop()

        self.cast = cast

        def bootstrap():
            main = greenlet.getcurrent()

            def receive(pattern=None, timeout=None):
                delayed = None
                b = None

                if timeout is not None:
                    delayed = timeout_helper(self, timeout)

                while b is None:
                    if pattern is None:
                        for (pat, b) in self.mailbox.items():
                            break
                    elif pattern in self.mailbox:
                        pat = pattern
                        b = self.mailbox[pat]
                    elif not isinstance(pattern, str):
                        for p in pattern:
                            if p in self.mailbox:
                                pat = p
                                b = self.mailbox[pat]
                    if b is None:
                        main.switch()
                    if self.mailbox.get('timeout') is not None:
                        b = self.mailbox['timeout']
                        b.pop(0)
                        if not len(b):
                            del self.mailbox['timeout']
                        raise Exception("timeout")

                if delayed is not None:
                    delayed.cancel()

                msg = b.pop(0)
                if not isinstance(msg, Address):
                    msg = json.loads(msg)
                if not len(b):
                    del self.mailbox[pat]
                if not isinstance(pattern, str):
                    return (pat, msg)
                return msg

            self.recv = receive

            def resume():
                try:
                    func(self, *args, **kw)
                except Exception, e:
                    print "Actor had exception:", e
                    traceback.print_exc(e)
                self.mailbox = None
                self.resume = lambda: None
                self.cast = lambda pat, msg: None
                self.spawn = None
                raise greenlet.GreenletExit

            me = greenlet.greenlet(resume)
            self.resume = me.switch
            self.resume()

        self.resume = bootstrap

        def connect(ip, port):
            dis.incref(self)
            myfd = actor_client_factory.cur_fd

            endpoints.TCP4ClientEndpoint(
                reactor, ip, port
            ).connect(actor_client_factory).addErrback(
                lambda result: self.cast("connectionMade", (myfd, False))
            )

            (fd, success) = self.recv("connectionMade")
            if not success:
                dis.decref(self)
                raise Exception("connection error")
            return ActorSocket(actor_client_factory.connecting.pop(fd))

        self.connect = connect

        def sleep(timeout):
            dis.incref(self)
            reactor.callLater(timeout, lambda: self.cast("timer", timeout))
            self.recv("timer")
            dis.decref(self)

        self.sleep = sleep


    def run(self):
        raise NotImplementedError("Implement in subclass")


class FileActor(Actor):
    def __init__(self, dis, filename, args, kw):
        Actor.__init__(self, dis, None, (filename, ), {})

    def run(self, filename, what=None):
        execfile(filename, {
            "recv": self.recv,
            "spawn": self.spawn,
            "sleep": self.sleep,
            "connect": self.connect})


def timeout_helper(a, time):
    return reactor.callLater(time, lambda: a.cast("timeout", time))


class Dispatcher(object):
    actor_class = Actor
    def __init__(self):
        self.ready_to_run = []
        self.outstanding_io = {}
        self.looping = False

    def incref(self, actor):
        self.outstanding_io[self] = self.outstanding_io.get(self, 0) + 1

    def decref(self, actor):
        self.outstanding_io[self] -= 1
        if not self.outstanding_io[self]:
            self.outstanding_io.pop(self)

    def loop(self):
        self.looping = True
        (rr, self.ready_to_run) = (self.ready_to_run, [])

        for a in rr:
            a.resume()

        self.looping = False
        if len(self.ready_to_run):
            reactor.callLater(0, self.loop)
        elif not len(self.outstanding_io):
            try:
                reactor.stop()
            except error.ReactorNotRunning, e:
                pass

    def spawn(self, func_or_fn, *args, **kw):
        if callable(func_or_fn):
            if isinstance(func_or_fn, type) and issubclass(func_or_fn, Actor):
                actor = func_or_fn(self, None, args, kw)
            else:
                actor = self.actor_class(self, func_or_fn, args, kw)
        else:
            actor = FileActor(self, func_or_fn, args, kw)
        self.ready_to_run.append(actor)
        return Address(actor)


def hi(act):
    con = act.connect('localhost', 80)
    con.send("GET / HTTP/1.0\r\nHost: localhost\r\n\r\n")
    got = con.recv()
    print "got # bytes:", len(got)
    act.recv('what')
    print "bye"
    b = act.spawn(bye)
    b.cast('asdf', 1)
    b.cast('qwer', 34)
    con.recv()


def bye(act):
    print "oh ok"
    while True:
        next = act.recv()
        print "oh ok", next


class SubclassTest(Actor):
    def run(self, foo):
        print "classy", foo
        v = self.recv()
        print "classy v", v


def timer(act):
    for x in range(6):
        act.sleep(0.666)
        print "timer!", 5 - x

def timer2(act):
    for x in range(11):
        act.sleep(0.333)
        print "timer2!", 10 - x


def select(act):
    while True:
        val = act.recv(("one", "two"))
        print "select", val


def refused(act):
    print "Producing connection error..."
    try:
        act.connect("localhost", 1)
    except:
        print "Connection error produced ok."
    else:
        raise Exception("Did not produce connection error")


def forever_alone(act):
    try:
        act.recv('hello', timeout=2)
    except:
        print "forever alone..."
    else:
        raise Exception("Did not timeout")


def pingpong(act, p):
    peer = act.recv('peer')
    for x in range(5):
        peer.cast('msg', 0)
        act.recv('msg')
        print p, x


d = Dispatcher()

a = d.spawn(hi)
c = d.spawn(SubclassTest, 'foo!')
f = d.spawn('foo.py')
d.spawn(timer)
d.spawn(timer2)
s = d.spawn(select)
d.spawn(refused)
d.spawn(forever_alone)
ping = d.spawn(pingpong, "pong")
pong = d.spawn(pingpong, "ping")

a.cast('what', {})
a.cast('ohno', {})
c.cast("woohoo", "yeahman")
f.cast("aloha", "foo.py")
s.cast("one", "asdf")
s.cast("garbage", "qwer")
s.cast("two", "asdf")
s.cast("one", "qwer")
s.cast("two", "qwer")
ping.cast('peer', pong)
pong.cast('peer', ping)

d.loop()
reactor.run()

