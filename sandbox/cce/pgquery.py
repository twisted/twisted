from twisted.internet import abstract, defer
from pyPgSQL import libpq

class PgAsyncConn(abstract.FileDescriptor):
    def __init__(self, dsn, reactor = None):
        abstract.FileDescriptor.__init__(self, reactor)
        self.conn = libpq.PQconnectdb(dsn)
        self.fileno = lambda: self.conn.socket
        self.active = None
        self.result = []
    def query(self, *args, **kwargs):
        self.active = defer.Deferred()
        self.conn.sendQuery(*args, **kwargs)
        self.startReading()
        return self.active
    def cleanup(self):
        defer = self.active
        self.result = []
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
            self.result.append(result)
    def connectionLost(self, reason):
        self.conn.finish()

if '__main__' == __name__:
    from twisted.internet import reactor
    db = PgAsyncConn("dbname=testing")
    d = db.query("SELECT now(); SELECT now();")
    def process(result):
        def dorow(result):
            print result.ntuples, result.nfields, result.getvalue(0,0)
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
