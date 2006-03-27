# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
# Author: Clark Evans  (cce@clarkevans.com)
# Stability: The API is stable, but the implementation may still
#            have one or more bugs; threads are tough.
#

""" flow.thread 

    Support for threads within a flow
"""

from __future__ import nested_scopes

from base import *
from twisted.python.failure import Failure
from twisted.internet import reactor
from time import sleep

class Threaded(Stage):
    """
    A stage which runs a blocking iterable in a separate thread

    This stage tunnels output from an iterable executed in a separate thread to
    the main thread.  This process is carried out by a result buffer, and
    returning Cooperate if the buffer is empty.  The wrapped iterable's
    __iter__ and next() methods will only be invoked in the spawned thread.

    This can be used in one of two ways, first, it can be extended via
    inheritance; with the functionality of the inherited code implementing
    next(), and using init() for initialization code to be run in the thread.

    If the iterable happens to have a chunked attribute, and that attribute is
    true, then this wrapper will assume that data arrives in chunks via a
    sequence instead of by values.

    For example::

        from __future__ import generators
        from twisted.internet import reactor, defer
        from twisted.flow import flow
        from twisted.flow.threads import Threaded

        def countSleep(index):
            from time import sleep
            for index in range(index):
                sleep(.3)
                print "sleep", index
                yield index

        def countCooperate(index):
            for index in range(index):
                yield flow.Cooperate(.1)
                print "cooperate", index
                yield "coop %s" % index

        d = flow.Deferred( flow.Merge(
                Threaded(countSleep(5)),
                countCooperate(5)))

        def prn(x):
            print x
            reactor.stop()
        d.addCallback(prn)
        reactor.run()
    """
    class Instruction(CallLater):
        def __init__(self):
            self.callable = None
            self.immediate = False
        def callLater(self, callable):
            if self.immediate:
                reactor.callLater(0,callable)
            else:
                self.callable = callable
        def __call__(self):
            callable = self.callable
            if callable:
                self.callable = None
                callable()

    def __init__(self, iterable, *trap):
        Stage.__init__(self, trap)
        self._iterable  = iterable
        self._cooperate = Threaded.Instruction()
        self.srcchunked = getattr(iterable, 'chunked', False)
        reactor.callInThread(self._process)
  
    def _process_result(self, val):
        if self.srcchunked:
            self.results.extend(val)
        else:
            self.results.append(val)
        self._cooperate()

    def _stopping(self):
        self.stop = True
        self._cooperate()

    def _process(self):
        try:
            self._iterable = iter(self._iterable)
        except: 
            self.failure = Failure()
        else:
            try:
                while True:
                    val = self._iterable.next()
                    reactor.callFromThread(self._process_result, val)
            except StopIteration:
                reactor.callFromThread(self._stopping)
            except: 
                self.failure = Failure()
                reactor.callFromThread(self._cooperate)
            self._cooperate.immediate = True

    def _yield(self):
        if self.results or self.stop or self.failure:
            return
        return self._cooperate


class QueryIterator:
    """
    Converts a database query into a result iterator

    Example usage::

        from __future__         import generators
        from twisted.enterprise import adbapi
        from twisted.internet   import reactor
        from twisted.flow import flow
        from twisted.flow.threads import QueryIterator, Threaded

        dbpool = adbapi.ConnectionPool("SomeDriver",host='localhost',
                     db='Database',user='User',passwd='Password')

        # # I test with...
        # from pyPgSQL import PgSQL
        # dbpool = PgSQL

        sql = '''
          (SELECT 'one')
        UNION ALL
          (SELECT 'two')
        UNION ALL
          (SELECT 'three')
        '''
        def consumer():
            print "executing"
            query = Threaded(QueryIterator(dbpool, sql))
            print "yielding"
            yield query
            print "done yeilding"
            for row in query:
                print "Processed result : ", row
                yield query

        from twisted.internet import reactor
        def finish(result):
            print "Deferred Complete : ", result
            reactor.stop()
        f = flow.Deferred(consumer())
        f.addBoth(finish)
        reactor.run()
    """

    def __init__(self, pool, sql, fetchmany=False, fetchall=False):
        self.curs = None
        self.sql = sql
        self.pool = pool
        if fetchmany: 
            self.next = self.next_fetchmany
            self.chunked = True
        if fetchall:
            self.next = self.next_fetchall
            self.chunked = True

    def __iter__(self):
        self.conn = self.pool.connect()
        self.curs = self.conn.cursor()
        self.curs.execute(self.sql)
        return self

    def next_fetchall(self):
        if self.curs:
            ret = self.curs.fetchall()
            self.curs = None
            self.conn = None
            return ret
        raise StopIteration
    
    def next_fetchmany(self):
        ret = self.curs.fetchmany()
        if not ret:
            self.curs = None
            self.conn = None
            raise StopIteration
        return ret

    def next(self):
        ret = self.curs.fetchone()
        if not ret: 
            self.curs = None
            self.conn = None
            raise StopIteration
        return ret

