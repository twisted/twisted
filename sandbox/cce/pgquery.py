import weakref
from twisted.internet import abstract, defer, error
from pyPgSQL import libpq

class PgAsyncConn(abstract.FileDescriptor):
    def __init__(self, pool):
        abstract.FileDescriptor.__init__(self, pool.reactor)
        self.pool = weakref.ref(pool)
        self.conn = libpq.PQconnectdb(pool.dsn)
        self.fileno = lambda: self.conn.socket
        self.active = None
        self.startReading()
    def query(self, *args, **kwargs):
        assert not self.active
        self.active = defer.Deferred()
        self.result = []
        self.conn.sendQuery(*args, **kwargs)
        return self.active
    def cleanup(self):
        assert self.active
        defer = self.active
        self.result = None
        self.active = None
        return defer
    def doRead(self):
        self.conn.consumeInput()
        while self.active and not self.conn.isBusy:
            try:
                result = self.conn.getResult()
            except:
                self.cleanup().errback(defer.failure.Failure())
                return
            if result is None:
                result = self.result
                if 1 == len(result):
                    result = result[0]
                self.cleanup().callback(result)
                return
            self.result.append(result)
    def connectionLost(self, reason):
        if self.active:
            self.cleanup().errback(\
                defer.failure.Failure(error.ConnectionLost))
        self.conn.finish()
        self.conn = None
    def __del__(self):
        try:
            if self.conn:
                self.pool().free(self)
        except:
            pass

class PgAsyncPool:
    def __init__(self, dsn, size = 5, reactor = None):
        self.dsn = dsn
        self.reactor = reactor
        self.waiting = []
        self.connect = []
        for i in range(size):
            self.connect.append(PgAsyncConn(self))
    def next(self):
        d = defer.Deferred()
        try:
            conn = self.connect.pop()
        except IndexError:
            self.waiting.append(d)
        else:
            d.callback(conn)
        return d
    def free(self, conn):
        if conn in self.connect:
            return
        try:
            d = self.writing.pop()
        except IndexError:
            self.connect.push(conn)
        else:
            d.callback(conn)

if '__main__' == __name__:
    from twisted.internet import reactor
    pool = PgAsyncPool("dbname=testing")
    d = pool.next()
    d.addCallback(lambda conn: conn.query(\
        "SELECT NULL; SELECT 1; SELECT '1'; SELECT now();"))
    def process(result):
        def dorow(result):
            val = result.getvalue(0,0)
            print result.ntuples, result.nfields, type(val), val
        if type(result) == type([]):
            for row in result:
                dorow(row)
        else:
            dorow(result)
    def badnews(failure):
        print "error", failure
    d.addCallback(process)
    d.addErrback(badnews)
    d.addCallback(lambda _: reactor.stop())
    reactor.run() 
