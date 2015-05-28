# -*- test-case-name: twext.enterprise.test.test_queue -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
L{twext.enterprise.queue} is an U{eventually consistent
<https://en.wikipedia.org/wiki/Eventual_consistency>} task-queueing system for
use by applications with multiple front-end servers talking to a single
database instance, that want to defer and parallelize work that involves
storing the results of computation.

By enqueuing with L{twisted.enterprise.queue}, you may guarantee that the work
will I{eventually} be done, and reliably commit to doing it in the future, but
defer it if it does not need to be done I{now}.

To pick a hypothetical example, let's say that you have a store which wants to
issue a promotional coupon based on a customer loyalty program, in response to
an administrator clicking on a button.  Determining the list of customers to
send the coupon to is quick: a simple query will get you all their names.
However, analyzing each user's historical purchase data is (A) time consuming
and (B) relatively isolated, so it would be good to do that in parallel, and it
would also be acceptable to have that happen at a later time, outside the
critical path.

Such an application might be implemented with this queueing system like so::

    from twext.enterprise.queue import WorkItem, queueFromTransaction
    from twext.enterprise.dal.parseschema import addSQLToSchema
    from twext.enterprise.dal.syntax import SchemaSyntax

    schemaModel = Schema()
    addSQLToSchema('''
        create table CUSTOMER (NAME varchar(255), ID integer primary key);
        create table PRODUCT (NAME varchar(255), ID integer primary key);
        create table PURCHASE (NAME varchar(255), WHEN timestamp,
                               CUSTOMER_ID integer references CUSTOMER,
                               PRODUCT_ID integer references PRODUCT;
        create table COUPON_WORK (WORK_ID integer primary key,
                                  CUSTOMER_ID integer references CUSTOMER);
        create table COUPON (ID integer primary key,
                            CUSTOMER_ID integer references customer,
                            AMOUNT integer);
    ''')
    schema = SchemaSyntax(schemaModel)

    class Coupon(Record, fromTable(schema.COUPON_WORK)):
        pass

    class CouponWork(WorkItem, fromTable(schema.COUPON_WORK)):
        @inlineCallbacks
        def doWork(self):
            purchases = yield Select(schema.PURCHASE,
                                     Where=schema.PURCHASE.CUSTOMER_ID
                                     == self.customerID).on(self.transaction)
            couponAmount = yield doSomeMathThatTakesAWhile(purchases)
            yield Coupon.create(customerID=self.customerID,
                                amount=couponAmount)

    @inlineCallbacks
    def makeSomeCoupons(txn):
        # Note, txn was started before, will be committed later...
        for customerID in (yield Select([schema.CUSTOMER.CUSTOMER_ID],
                                        From=schema.CUSTOMER).on(txn)):
            # queuer is a provider of IQueuer, of which there are several
            # implementations in this module.
            queuer.enqueueWork(txn, CouponWork, customerID=customerID)
"""

from functools import wraps
from datetime import datetime

from zope.interface import implements

from twisted.application.service import MultiService
from twisted.internet.protocol import Factory
from twisted.internet.defer import (
    inlineCallbacks, returnValue, Deferred, passthru, succeed
)
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.protocols.amp import AMP, Command, Integer, Argument, String
from twisted.python.reflect import qual
from twisted.python import log

from twext.enterprise.dal.syntax import SchemaSyntax, Lock, NamedValue

from twext.enterprise.dal.model import ProcedureCall
from twext.enterprise.dal.record import Record, fromTable, NoSuchRecord
from twisted.python.failure import Failure

from twext.enterprise.dal.model import Table, Schema, SQLType, Constraint
from twisted.internet.endpoints import TCP4ServerEndpoint
from twext.enterprise.ienterprise import IQueuer
from zope.interface.interface import Interface
from twext.enterprise.locking import NamedLock


class _IWorkPerformer(Interface):
    """
    An object that can perform work.

    Internal interface; implemented by several classes here since work has to
    (in the worst case) pass from worker->controller->controller->worker.
    """

    def performWork(table, workID): #@NoSelf
        """
        @param table: The table where work is waiting.
        @type table: L{TableSyntax}

        @param workID: The primary key identifier of the given work.
        @type workID: L{int}

        @return: a L{Deferred} firing with an empty dictionary when the work is
            complete.
        @rtype: L{Deferred} firing L{dict}
        """



def makeNodeSchema(inSchema):
    """
    Create a self-contained schema for L{NodeInfo} to use, in C{inSchema}.

    @param inSchema: a L{Schema} to add the node-info table to.
    @type inSchema: L{Schema}

    @return: a schema with just the one table.
    """
    # Initializing this duplicate schema avoids a circular dependency, but this
    # should really be accomplished with independent schema objects that the
    # transaction is made aware of somehow.
    NodeTable = Table(inSchema, "NODE_INFO")

    NodeTable.addColumn("HOSTNAME", SQLType("varchar", 255))
    NodeTable.addColumn("PID", SQLType("integer", None))
    NodeTable.addColumn("PORT", SQLType("integer", None))
    NodeTable.addColumn("TIME", SQLType("timestamp", None)).setDefaultValue(
        # Note: in the real data structure, this is actually a not-cleaned-up
        # sqlparse internal data structure, but it *should* look closer to
        # this.
        ProcedureCall("timezone", ["UTC", NamedValue("CURRENT_TIMESTAMP")])
    )
    for column in NodeTable.columns:
        NodeTable.tableConstraint(Constraint.NOT_NULL, [column.name])
    NodeTable.primaryKey = [
        NodeTable.columnNamed("HOSTNAME"),
        NodeTable.columnNamed("PORT"),
    ]

    return inSchema

NodeInfoSchema = SchemaSyntax(makeNodeSchema(Schema(__file__)))



@inlineCallbacks
def inTransaction(transactionCreator, operation):
    """
    Perform the given operation in a transaction, committing or aborting as
    required.

    @param transactionCreator: a 0-arg callable that returns an
        L{IAsyncTransaction}

    @param operation: a 1-arg callable that takes an L{IAsyncTransaction} and
        returns a value.

    @return: a L{Deferred} that fires with C{operation}'s result or fails with
        its error, unless there is an error creating, aborting or committing
        the transaction.
    """
    txn = transactionCreator()
    try:
        result = yield operation(txn)
    except:
        f = Failure()
        yield txn.abort()
        returnValue(f)
    else:
        yield txn.commit()
        returnValue(result)



def astimestamp(v):
    """
    Convert the given datetime to a POSIX timestamp.
    """
    return (v - datetime.utcfromtimestamp(0)).total_seconds()



class TableSyntaxByName(Argument):
    """
    Serialize and deserialize L{TableSyntax} objects for an AMP protocol with
    an attached schema.
    """

    def fromStringProto(self, inString, proto):
        """
        Convert the name of the table into a table, given a C{proto} with an
        attached C{schema}.

        @param inString: the name of a table, as utf-8 encoded bytes
        @type inString: L{bytes}

        @param proto: an L{SchemaAMP}
        """
        return getattr(proto.schema, inString.decode("UTF-8"))


    def toString(self, inObject):
        """
        Convert a L{TableSyntax} object into just its name for wire transport.

        @param inObject: a table.
        @type inObject: L{TableSyntax}

        @return: the name of that table
        @rtype: L{bytes}
        """
        return inObject.model.name.encode("UTF-8")



class NodeInfo(Record, fromTable(NodeInfoSchema.NODE_INFO)):
    """
    A L{NodeInfo} is information about a currently-active Node process.
    """

    def endpoint(self, reactor):
        """
        Create an L{IStreamServerEndpoint} that will talk to the node process
        that is described by this L{NodeInfo}.

        @return: an endpoint that will connect to this host.
        @rtype: L{IStreamServerEndpoint}
        """
        return TCP4ClientEndpoint(reactor, self.hostname, self.port)



def abstract(thunk):
    """
    The decorated function is abstract.

    @note: only methods are currently supported.
    """
    @classmethod
    @wraps(thunk)
    def inner(cls, *a, **k):
        raise NotImplementedError(
            qual(cls) + " does not implement " + thunk.func_name
        )
    return inner



class WorkItem(Record):
    """
    A L{WorkItem} is an item of work which may be stored in a database, then
    executed later.

    L{WorkItem} is an abstract class, since it is a L{Record} with no table
    associated via L{fromTable}.  Concrete subclasses must associate a specific
    table by inheriting like so::

        class MyWorkItem(WorkItem, fromTable(schema.MY_TABLE)):

    Concrete L{WorkItem}s should generally not be created directly; they are
    both created and thereby implicitly scheduled to be executed by calling
    L{enqueueWork <twext.enterprise.ienterprise.IQueuer.enqueueWork>} with the
    appropriate L{WorkItem} concrete subclass.  There are different queue
    implementations (L{PeerConnectionPool} and L{LocalQueuer}, for example), so
    the exact timing and location of the work execution may differ.

    L{WorkItem}s may be constrained in the ordering and timing of their
    execution, to control concurrency and for performance reasons respectively.

    Although all the usual database mutual-exclusion rules apply to work
    executed in L{WorkItem.doWork}, implicit database row locking is not always
    the best way to manage concurrency.  They have some problems, including:

        - implicit locks are easy to accidentally acquire out of order, which
          can lead to deadlocks

        - implicit locks are easy to forget to acquire correctly - for example,
          any read operation which subsequently turns into a write operation
          must have been acquired with C{Select(..., ForUpdate=True)}, but it
          is difficult to consistently indicate that methods which abstract out
          read operations must pass this flag in certain cases and not others.

        - implicit locks are held until the transaction ends, which means that
          if expensive (long-running) queue operations share the same lock with
          cheap (short-running) queue operations or user interactions, the
          cheap operations all have to wait for the expensive ones to complete,
          but continue to consume whatever database resources they were using.

    In order to ameliorate these problems with potentially concurrent work
    that uses the same resources, L{WorkItem} provides a database-wide mutex
    that is automatically acquired at the beginning of the transaction and
    released at the end.  To use it, simply L{align
    <twext.enterprise.dal.record.Record.namingConvention>} the C{group}
    attribute on your L{WorkItem} subclass with a column holding a string
    (varchar).  L{WorkItem} subclasses with the same value for C{group} will
    not execute their C{doWork} methods concurrently.  Furthermore, if the lock
    cannot be quickly acquired, database resources associated with the
    transaction attempting it will be released, and the transaction rolled back
    until a future transaction I{can} can acquire it quickly.  If you do not
    want any limits to concurrency, simply leave it set to C{None}.

    In some applications it's possible to coalesce work together; to grab
    multiple L{WorkItem}s in one C{doWork} transaction.  All you need to do is
    to delete the rows which back other L{WorkItem}s from the database, and
    they won't be processed.  Using the C{group} attribute, you can easily
    prevent concurrency so that you can easily group these items together and
    remove them as a set (otherwise, other workers might be attempting to
    concurrently work on them and you'll get deletion errors).

    However, if doing more work at once is less expensive, and you want to
    avoid processing lots of individual rows in tiny transactions, you may also
    delay the execution of a L{WorkItem} by setting its C{notBefore} attribute.
    This must be backed by a database timestamp, so that processes which happen
    to be restarting and examining the work to be done in the database don't
    jump the gun and do it too early.

    @cvar workID: the unique identifier (primary key) for items of this type.
        On an instance of a concrete L{WorkItem} subclass, this attribute must
        be an integer; on the concrete L{WorkItem} subclass itself, this
        attribute must be a L{twext.enterprise.dal.syntax.ColumnSyntax}.  Note
        that this is automatically taken care of if you simply have a
        corresponding C{work_id} column in the associated L{fromTable} on your
        L{WorkItem} subclass.  This column must be unique, and it must be an
        integer.  In almost all cases, this column really ought to be filled
        out by a database-defined sequence; if not, you need some other
        mechanism for establishing a cluster-wide sequence.
    @type workID: L{int} on instance,
        L{twext.enterprise.dal.syntax.ColumnSyntax} on class.

    @cvar notBefore: the timestamp before which this item should I{not} be
        processed.  If unspecified, this should be the date and time of the
        creation of the L{WorkItem}.
    @type notBefore: L{datetime.datetime} on instance,
        L{twext.enterprise.dal.syntax.ColumnSyntax} on class.

    @ivar group: If not C{None}, a unique-to-the-database identifier for which
        only one L{WorkItem} will execute at a time.
    @type group: L{unicode} or L{NoneType}
    """

    group = None


    @abstract
    def doWork(self):
        """
        Subclasses must implement this to actually perform the queued work.

        This method will be invoked in a worker process.

        This method does I{not} need to delete the row referencing it; that
        will be taken care of by the job queueing machinery.
        """

    @classmethod
    def forTable(cls, table):
        """
        Look up a work-item class given a particular L{TableSyntax}.  Factoring
        this correctly may place it into L{twext.enterprise.record.Record}
        instead; it is probably generally useful to be able to look up a mapped
        class from a table.

        @param table: the table to look up
        @type table: L{twext.enterprise.dal.model.Table}

        @return: the relevant subclass
        @rtype: L{type}
        """
        tableName = table.model.name
        for subcls in cls.__subclasses__():
            clstable = getattr(subcls, "table", None)
            if table == clstable:
                return subcls
        raise KeyError("No mapped {0} class for {1}.".format(
            cls, tableName
        ))



class PerformWork(Command):
    """
    Notify another process that it must do some work that has been persisted to
    the database, by informing it of the table and the ID where said work has
    been persisted.
    """

    arguments = [
        ("table", TableSyntaxByName()),
        ("workID", Integer()),
    ]
    response = []



class ReportLoad(Command):
    """
    Notify another node of the total, current load for this whole node (all of
    its workers).
    """
    arguments = [
        ("load", Integer())
    ]
    response = []



class IdentifyNode(Command):
    """
    Identify this node to its peer.  The connector knows which hostname it's
    looking for, and which hostname it considers itself to be, only the
    initiator (not the listener) issues this command.  This command is
    necessary because we don't want to rely on DNS; if reverse DNS weren't set
    up perfectly, the listener would not be able to identify its peer, and it
    is easier to modify local configuration so that L{socket.getfqdn} returns
    the right value than to ensure that DNS doesself.
    """

    arguments = [
        ("host", String()),
        ("port", Integer()),
    ]



class SchemaAMP(AMP):
    """
    An AMP instance which also has a L{Schema} attached to it.

    @ivar schema: The schema to look up L{TableSyntaxByName} arguments in.
    @type schema: L{Schema}
    """

    def __init__(self, schema, boxReceiver=None, locator=None):
        self.schema = schema
        super(SchemaAMP, self).__init__(boxReceiver, locator)



class ConnectionFromPeerNode(SchemaAMP):
    """
    A connection to a peer node.  Symmetric; since the "client" and the
    "server" both serve the same role, the logic is the same in every node.

    @ivar localWorkerPool: the pool of local worker procesess that can process
        queue work.
    @type localWorkerPool: L{WorkerConnectionPool}

    @ivar _reportedLoad: The number of outstanding requests being processed by
        the peer of this connection, from all requestors (both the host of this
        connection and others), as last reported by the most recent
        L{ReportLoad} message received from the peer.
    @type _reportedLoad: L{int}

    @ivar _bonusLoad: The number of additional outstanding requests being
        processed by the peer of this connection; the number of requests made
        by the host of this connection since the last L{ReportLoad} message.
    @type _bonusLoad: L{int}
    """
    implements(_IWorkPerformer)

    def __init__(self, peerPool, boxReceiver=None, locator=None):
        """
        Initialize this L{ConnectionFromPeerNode} with a reference to a
        L{PeerConnectionPool}, as well as required initialization arguments for
        L{AMP}.

        @param peerPool: the connection pool within which this
            L{ConnectionFromPeerNode} is a participant.
        @type peerPool: L{PeerConnectionPool}

        @see: L{AMP.__init__}
        """
        self.peerPool = peerPool
        self._bonusLoad = 0
        self._reportedLoad = 0
        super(ConnectionFromPeerNode, self).__init__(
            peerPool.schema, boxReceiver, locator
        )


    def reportCurrentLoad(self):
        """
        Report the current load for the local worker pool to this peer.
        """
        return self.callRemote(ReportLoad, load=self.totalLoad())


    @ReportLoad.responder
    def reportedLoad(self, load):
        """
        The peer reports its load.
        """
        self._reportedLoad = (load - self._bonusLoad)
        return {}


    def startReceivingBoxes(self, sender):
        """
        Connection is up and running; add this to the list of active peers.
        """
        r = super(ConnectionFromPeerNode, self).startReceivingBoxes(sender)
        self.peerPool.addPeerConnection(self)
        return r


    def stopReceivingBoxes(self, reason):
        """
        The connection has shut down; remove this from the list of active
        peers.
        """
        self.peerPool.removePeerConnection(self)
        r = super(ConnectionFromPeerNode, self).stopReceivingBoxes(reason)
        return r


    def currentLoadEstimate(self):
        """
        What is the current load estimate for this peer?

        @return: The number of full "slots", i.e. currently-being-processed
            queue items (and other items which may contribute to this process's
            load, such as currently-being-processed client requests).
        @rtype: L{int}
        """
        return self._reportedLoad + self._bonusLoad


    def performWork(self, table, workID):
        """
        A L{local worker connection <ConnectionFromWorker>} is asking this
        specific peer node-controller process to perform some work, having
        already determined that it's appropriate.

        @see: L{_IWorkPerformer.performWork}
        """
        d = self.callRemote(PerformWork, table=table, workID=workID)
        self._bonusLoad += 1

        @d.addBoth
        def performed(result):
            self._bonusLoad -= 1
            return result

        @d.addCallback
        def success(result):
            return None

        return d


    @PerformWork.responder
    def dispatchToWorker(self, table, workID):
        """
        A remote peer node has asked this node to do some work; dispatch it to
        a local worker on this node.

        @param table: the table to work on.
        @type table: L{TableSyntax}

        @param workID: the identifier within the table.
        @type workID: L{int}

        @return: a L{Deferred} that fires when the work has been completed.
        """
        d = self.peerPool.performWorkForPeer(table, workID)
        d.addCallback(lambda ignored: {})
        return d


    @IdentifyNode.responder
    def identifyPeer(self, host, port):
        self.peerPool.mapPeer(host, port, self)
        return {}



class WorkerConnectionPool(object):
    """
    A pool of L{ConnectionFromWorker}s.

    L{WorkerConnectionPool} also implements the same implicit protocol as a
    L{ConnectionFromPeerNode}, but one that dispenses work to the local worker
    processes rather than to a remote connection pool.
    """
    implements(_IWorkPerformer)

    def __init__(self, maximumLoadPerWorker=5):
        self.workers = []
        self.maximumLoadPerWorker = maximumLoadPerWorker


    def addWorker(self, worker):
        """
        Add a L{ConnectionFromWorker} to this L{WorkerConnectionPool} so that
        it can be selected.
        """
        self.workers.append(worker)


    def removeWorker(self, worker):
        """
        Remove a L{ConnectionFromWorker} from this L{WorkerConnectionPool} that
        was previously added.
        """
        self.workers.remove(worker)


    def hasAvailableCapacity(self):
        """
        Does this worker connection pool have any local workers who have spare
        hasAvailableCapacity to process another queue item?
        """
        for worker in self.workers:
            if worker.currentLoad < self.maximumLoadPerWorker:
                return True
        return False


    def allWorkerLoad(self):
        """
        The total load of all currently connected workers.
        """
        return sum(worker.currentLoad for worker in self.workers)


    def _selectLowestLoadWorker(self):
        """
        Select the local connection with the lowest current load, or C{None} if
        all workers are too busy.

        @return: a worker connection with the lowest current load.
        @rtype: L{ConnectionFromWorker}
        """
        return sorted(self.workers[:], key=lambda w: w.currentLoad)[0]


    def performWork(self, table, workID):
        """
        Select a local worker that is idle enough to perform the given work,
        then ask them to perform it.

        @param table: The table where work is waiting.
        @type table: L{TableSyntax}

        @param workID: The primary key identifier of the given work.
        @type workID: L{int}

        @return: a L{Deferred} firing with an empty dictionary when the work is
            complete.
        @rtype: L{Deferred} firing L{dict}
        """
        preferredWorker = self._selectLowestLoadWorker()
        result = preferredWorker.performWork(table, workID)
        return result



class ConnectionFromWorker(SchemaAMP):
    """
    An individual connection from a worker, as seem from the master's
    perspective.  L{ConnectionFromWorker}s go into a L{WorkerConnectionPool}.
    """

    def __init__(self, peerPool, boxReceiver=None, locator=None):
        super(ConnectionFromWorker, self).__init__(peerPool.schema,
                                                   boxReceiver, locator)
        self.peerPool = peerPool
        self._load = 0


    @property
    def currentLoad(self):
        """
        What is the current load of this worker?
        """
        return self._load


    def startReceivingBoxes(self, sender):
        """
        Start receiving AMP boxes from the peer.  Initialize all necessary
        state.
        """
        result = super(ConnectionFromWorker, self).startReceivingBoxes(sender)
        self.peerPool.workerPool.addWorker(self)
        return result


    def stopReceivingBoxes(self, reason):
        """
        AMP boxes will no longer be received.
        """
        result = super(ConnectionFromWorker, self).stopReceivingBoxes(reason)
        self.peerPool.workerPool.removeWorker(self)
        return result


    @PerformWork.responder
    def performWork(self, table, workID):
        """
        Dispatch work to this worker.

        @see: The responder for this should always be
            L{ConnectionFromController.actuallyReallyExecuteWorkHere}.
        """
        d = self.callRemote(PerformWork, table=table, workID=workID)
        self._load += 1

        @d.addBoth
        def f(result):
            self._load -= 1
            return result

        return d



class ConnectionFromController(SchemaAMP):
    """
    A L{ConnectionFromController} is the connection to a node-controller
    process, in a worker process.  It processes requests from its own
    controller to do work.  It is the opposite end of the connection from
    L{ConnectionFromWorker}.
    """
    implements(IQueuer)

    def __init__(self, transactionFactory, schema, whenConnected,
                 boxReceiver=None, locator=None):
        super(ConnectionFromController, self).__init__(schema,
                                                       boxReceiver, locator)
        self.transactionFactory = transactionFactory
        self.whenConnected = whenConnected
        # FIXME: Glyph it appears WorkProposal expects this to have reactor...
        from twisted.internet import reactor
        self.reactor = reactor


    def startReceivingBoxes(self, sender):
        super(ConnectionFromController, self).startReceivingBoxes(sender)
        self.whenConnected(self)


    def choosePerformer(self):
        """
        To conform with L{WorkProposal}'s expectations, which may run in either
        a controller (against a L{PeerConnectionPool}) or in a worker (against
        a L{ConnectionFromController}), this is implemented to always return
        C{self}, since C{self} is also an object that has a C{performWork}
        method.
        """
        return self


    def performWork(self, table, workID):
        """
        Ask the controller to perform some work on our behalf.
        """
        return self.callRemote(PerformWork, table=table, workID=workID)


    def enqueueWork(self, txn, workItemType, **kw):
        """
        There is some work to do.  Do it, ideally someplace else, ideally in
        parallel.  Later, let the caller know that the work has been completed
        by firing a L{Deferred}.

        @param workItemType: The type of work item to be enqueued.
        @type workItemType: A subtype of L{WorkItem}

        @param kw: The parameters to construct a work item.
        @type kw: keyword parameters to C{workItemType.create}, i.e.
            C{workItemType.__init__}

        @return: an object that can track the enqueuing and remote execution of
            this work.
        @rtype: L{WorkProposal}
        """
        wp = WorkProposal(self, txn, workItemType, kw)
        wp._start()
        return wp


    @PerformWork.responder
    def actuallyReallyExecuteWorkHere(self, table, workID):
        """
        This is where it's time to actually do the work.  The controller
        process has instructed this worker to do it; so, look up the data in
        the row, and do it.
        """
        d = ultimatelyPerform(self.transactionFactory, table, workID)
        d.addCallback(lambda ignored: {})
        return d



def ultimatelyPerform(txnFactory, table, workID):
    """
    Eventually, after routing the work to the appropriate place, somebody
    actually has to I{do} it.

    @param txnFactory: a 0- or 1-argument callable that creates an
        L{IAsyncTransaction}
    @type txnFactory: L{callable}

    @param table: the table object that corresponds to the necessary work item
    @type table: L{twext.enterprise.dal.syntax.TableSyntax}

    @param workID: the ID of the work to be performed
    @type workID: L{int}

    @return: a L{Deferred} which fires with C{None} when the work has been
        performed, or fails if the work can't be performed.
    """
    @inlineCallbacks
    def work(txn):
        workItemClass = WorkItem.forTable(table)
        try:
            workItem = yield workItemClass.load(txn, workID)
            if workItem.group is not None:
                yield NamedLock.acquire(txn, workItem.group)
            # TODO: what if we fail?  error-handling should be recorded
            # someplace, the row should probably be marked, re-tries should be
            # triggerable administratively.
            yield workItem.delete()
            # TODO: verify that workID is the primary key someplace.
            yield workItem.doWork()
        except NoSuchRecord:
            # The record has already been removed
            pass

    return inTransaction(txnFactory, work)



class LocalPerformer(object):
    """
    Implementor of C{performWork} that does its work in the local process,
    regardless of other conditions.
    """
    implements(_IWorkPerformer)

    def __init__(self, txnFactory):
        """
        Create this L{LocalPerformer} with a transaction factory.
        """
        self.txnFactory = txnFactory


    def performWork(self, table, workID):
        """
        Perform the given work right now.
        """
        return ultimatelyPerform(self.txnFactory, table, workID)



class WorkerFactory(Factory, object):
    """
    Factory, to be used as the client to connect from the worker to the
    controller.
    """

    def __init__(self, transactionFactory, schema, whenConnected):
        """
        Create a L{WorkerFactory} with a transaction factory and a schema.
        """
        self.transactionFactory = transactionFactory
        self.schema = schema
        self.whenConnected = whenConnected


    def buildProtocol(self, addr):
        """
        Create a L{ConnectionFromController} connected to the
        transactionFactory and store.
        """
        return ConnectionFromController(self.transactionFactory, self.schema,
                                        self.whenConnected)



class TransactionFailed(Exception):
    """
    A transaction failed.
    """



def _cloneDeferred(d):
    """
    Make a new Deferred, adding callbacks to C{d}.

    @return: another L{Deferred} that fires with C{d's} result when C{d} fires.
    @rtype: L{Deferred}
    """
    d2 = Deferred()
    d.chainDeferred(d2)
    return d2



class WorkProposal(object):
    """
    A L{WorkProposal} is a proposal for work that will be executed, perhaps on
    another node, perhaps in the future.

    @ivar _chooser: The object which will choose where the work in this
        proposal gets performed.  This must have both a C{choosePerformer}
        method and a C{reactor} attribute, providing an L{IReactorTime}.
    @type _chooser: L{PeerConnectionPool} or L{LocalQueuer}

    @ivar txn: The transaction where the work will be enqueued.
    @type txn: L{IAsyncTransaction}

    @ivar workItemType: The type of work to be enqueued by this L{WorkProposal}
    @type workItemType: L{WorkItem} subclass

    @ivar kw: The keyword arguments to pass to C{self.workItemType.create} to
        construct it.
    @type kw: L{dict}
    """

    def __init__(self, chooser, txn, workItemType, kw):
        self._chooser = chooser
        self.txn = txn
        self.workItemType = workItemType
        self.kw = kw
        self._whenProposed = Deferred()
        self._whenExecuted = Deferred()
        self._whenCommitted = Deferred()
        self.workItem = None


    def _start(self):
        """
        Execute this L{WorkProposal} by creating the work item in the database,
        waiting for the transaction where that addition was completed to
        commit, and asking the local node controller process to do the work.
        """
        created = self.workItemType.create(self.txn, **self.kw)

        def whenCreated(item):
            self.workItem = item
            self._whenProposed.callback(self)

            @self.txn.postCommit
            def whenDone():
                self._whenCommitted.callback(self)

                def maybeLater():
                    performer = self._chooser.choosePerformer()

                    @passthru(
                        performer.performWork(item.table, item.workID)
                        .addCallback
                    )
                    def performed(result):
                        self._whenExecuted.callback(self)

                    @performed.addErrback
                    def notPerformed(why):
                        self._whenExecuted.errback(why)

                reactor = self._chooser.reactor
                when = max(0, astimestamp(item.notBefore) - reactor.seconds())
                # TODO: Track the returned DelayedCall so it can be stopped
                # when the service stops.
                self._chooser.reactor.callLater(when, maybeLater)

            @self.txn.postAbort
            def whenFailed():
                self._whenCommitted.errback(TransactionFailed)

        def whenNotCreated(failure):
            self._whenProposed.errback(failure)

        created.addCallbacks(whenCreated, whenNotCreated)


    def whenExecuted(self):
        """
        Let the caller know when the proposed work has been fully executed.

        @note: The L{Deferred} returned by C{whenExecuted} should be used with
            extreme caution.  If an application decides to do any
            database-persistent work as a result of this L{Deferred} firing,
            that work I{may be lost} as a result of a service being normally
            shut down between the time that the work is scheduled and the time
            that it is executed.  So, the only things that should be added as
            callbacks to this L{Deferred} are those which are ephemeral, in
            memory, and reflect only presentation state associated with the
            user's perception of the completion of work, not logical chains of
            work which need to be completed in sequence; those should all be
            completed within the transaction of the L{WorkItem.doWork} that
            gets executed.

        @return: a L{Deferred} that fires with this L{WorkProposal} when the
            work has been completed remotely.
        """
        return _cloneDeferred(self._whenExecuted)


    def whenProposed(self):
        """
        Let the caller know when the work has been proposed; i.e. when the work
        is first transmitted to the database.

        @return: a L{Deferred} that fires with this L{WorkProposal} when the
            relevant commands have been sent to the database to create the
            L{WorkItem}, and fails if those commands do not succeed for some
            reason.
        """
        return _cloneDeferred(self._whenProposed)


    def whenCommitted(self):
        """
        Let the caller know when the work has been committed to; i.e. when the
        transaction where the work was proposed has been committed to the
        database.

        @return: a L{Deferred} that fires with this L{WorkProposal} when the
            relevant transaction has been committed, or fails if the
            transaction is not committed for any reason.
        """
        return _cloneDeferred(self._whenCommitted)



class _BaseQueuer(object):
    implements(IQueuer)

    def __init__(self):
        super(_BaseQueuer, self).__init__()
        self.proposalCallbacks = set()


    def callWithNewProposals(self, callback):
        self.proposalCallbacks.add(callback)


    def transferProposalCallbacks(self, newQueuer):
        newQueuer.proposalCallbacks = self.proposalCallbacks
        return newQueuer


    def enqueueWork(self, txn, workItemType, **kw):
        """
        There is some work to do.  Do it, someplace else, ideally in parallel.
        Later, let the caller know that the work has been completed by firing a
        L{Deferred}.

        @param workItemType: The type of work item to be enqueued.
        @type workItemType: A subtype of L{WorkItem}

        @param kw: The parameters to construct a work item.
        @type kw: keyword parameters to C{workItemType.create}, i.e.
            C{workItemType.__init__}

        @return: an object that can track the enqueuing and remote execution of
            this work.
        @rtype: L{WorkProposal}
        """
        wp = WorkProposal(self, txn, workItemType, kw)
        wp._start()
        for callback in self.proposalCallbacks:
            callback(wp)
        return wp



class PeerConnectionPool(_BaseQueuer, MultiService, object):
    """
    Each node has a L{PeerConnectionPool} connecting it to all the other nodes
    currently active on the same database.

    @ivar hostname: The hostname where this node process is running, as
        reported by the local host's configuration.  Possibly this should be
        obtained via C{config.ServerHostName} instead of C{socket.getfqdn()};
        although hosts within a cluster may be configured with the same
        C{ServerHostName}; TODO need to confirm.
    @type hostname: L{bytes}

    @ivar thisProcess: a L{NodeInfo} representing this process, which is
        initialized when this L{PeerConnectionPool} service is started via
        C{startService}.  May be C{None} if this service is not fully started
        up or if it is shutting down.
    @type thisProcess: L{NodeInfo}

    @ivar queueProcessTimeout: The amount of time after a L{WorkItem} is
        scheduled to be processed (its C{notBefore} attribute) that it is
        considered to be "orphaned" and will be run by a lost-work check rather
        than waiting for it to be requested.  By default, 10 minutes.
    @type queueProcessTimeout: L{float} (in seconds)

    @ivar queueDelayedProcessInterval: The amount of time between database
        pings, i.e. checks for over-due queue items that might have been
        orphaned by a controller process that died mid-transaction.  This is
        how often the shared database should be pinged by I{all} nodes (i.e.,
        all controller processes, or each instance of L{PeerConnectionPool});
        each individual node will ping commensurately less often as more nodes
        join the database.
    @type queueDelayedProcessInterval: L{float} (in seconds)

    @ivar reactor: The reactor used for scheduling timed events.
    @type reactor: L{IReactorTime} provider.

    @ivar peers: The list of currently connected peers.
    @type peers: L{list} of L{PeerConnectionPool}
    """
    implements(IQueuer)

    from socket import getfqdn
    from os import getpid
    getfqdn = staticmethod(getfqdn)
    getpid = staticmethod(getpid)

    queueProcessTimeout = (10.0 * 60.0)
    queueDelayedProcessInterval = (60.0)

    def __init__(self, reactor, transactionFactory, ampPort, schema):
        """
        Initialize a L{PeerConnectionPool}.

        @param ampPort: The AMP TCP port number to listen on for inter-host
            communication.  This must be an integer (and not, say, an endpoint,
            or an endpoint description) because we need to communicate it to
            the other peers in the cluster in a way that will be meaningful to
            them as clients.
        @type ampPort: L{int}

        @param transactionFactory: a 0- or 1-argument callable that produces an
            L{IAsyncTransaction}

        @param schema: The schema which contains all the tables associated with
            the L{WorkItem}s that this L{PeerConnectionPool} will process.
        @type schema: L{Schema}
        """
        super(PeerConnectionPool, self).__init__()
        self.reactor = reactor
        self.transactionFactory = transactionFactory
        self.hostname = self.getfqdn()
        self.pid = self.getpid()
        self.ampPort = ampPort
        self.thisProcess = None
        self.workerPool = WorkerConnectionPool()
        self.peers = []
        self.mappedPeers = {}
        self.schema = schema
        self._startingUp = None
        self._listeningPort = None
        self._lastSeenTotalNodes = 1
        self._lastSeenNodeIndex = 1


    def addPeerConnection(self, peer):
        """
        Add a L{ConnectionFromPeerNode} to the active list of peers.
        """
        self.peers.append(peer)


    def totalLoad(self):
        return self.workerPool.allWorkerLoad()


    def workerListenerFactory(self):
        """
        Factory that listens for connections from workers.
        """
        f = Factory()
        f.buildProtocol = lambda addr: ConnectionFromWorker(self)
        return f


    def removePeerConnection(self, peer):
        """
        Remove a L{ConnectionFromPeerNode} to the active list of peers.
        """
        self.peers.remove(peer)


    def choosePerformer(self, onlyLocally=False):
        """
        Choose a peer to distribute work to based on the current known slot
        occupancy of the other nodes.  Note that this will prefer distributing
        work to local workers until the current node is full, because that
        should be lower-latency.  Also, if no peers are available, work will be
        submitted locally even if the worker pool is already over-subscribed.

        @return: the chosen peer.
        @rtype: L{_IWorkPerformer} L{ConnectionFromPeerNode} or
            L{WorkerConnectionPool}
        """
        if self.workerPool.hasAvailableCapacity():
            return self.workerPool

        if self.peers and not onlyLocally:
            return sorted(self.peers, key=lambda p: p.currentLoadEstimate())[0]
        else:
            return LocalPerformer(self.transactionFactory)


    def performWorkForPeer(self, table, workID):
        """
        A peer has requested us to perform some work; choose a work performer
        local to this node, and then execute it.
        """
        performer = self.choosePerformer(onlyLocally=True)
        return performer.performWork(table, workID)


    def allWorkItemTypes(self):
        """
        Load all the L{WorkItem} types that this node can process and return
        them.

        @return: L{list} of L{type}
        """
        # TODO: For completeness, this may need to involve a plugin query to
        # make sure that all WorkItem subclasses are imported first.
        for workItemSubclass in WorkItem.__subclasses__():
            # TODO: It might be a good idea to offload this table-filtering to
            # SchemaSyntax.__contains__, adding in some more structure-
            # comparison of similarly-named tables.  For now a name check is
            # sufficient.
            if workItemSubclass.table.model.name in set([x.model.name for x in
                                                         self.schema]):
                yield workItemSubclass


    def totalNumberOfNodes(self):
        """
        How many nodes are there, total?

        @return: the maximum number of other L{PeerConnectionPool} instances
            that may be connected to the database described by
            C{self.transactionFactory}.  Note that this is not the current
            count by connectivity, but the count according to the database.
        @rtype: L{int}
        """
        # TODO
        return self._lastSeenTotalNodes


    def nodeIndex(self):
        """
        What ordinal does this node, i.e. this instance of
        L{PeerConnectionPool}, occupy within the ordered set of all nodes
        connected to the database described by C{self.transactionFactory}?

        @return: the index of this node within the total collection.  For
            example, if this L{PeerConnectionPool} is 6 out of 30, this method
            will return C{6}.
        @rtype: L{int}
        """
        # TODO
        return self._lastSeenNodeIndex


    def _periodicLostWorkCheck(self):
        """
        Periodically, every node controller has to check to make sure that work
        hasn't been dropped on the floor by someone.  In order to do that it
        queries each work-item table.
        """
        @inlineCallbacks
        def workCheck(txn):
            if self.thisProcess:
                nodes = [(node.hostname, node.port) for node in
                         (yield self.activeNodes(txn))]
                nodes.sort()
                self._lastSeenTotalNodes = len(nodes)
                self._lastSeenNodeIndex = nodes.index(
                    (self.thisProcess.hostname, self.thisProcess.port)
                )

            for itemType in self.allWorkItemTypes():
                tooLate = datetime.utcfromtimestamp(
                    self.reactor.seconds() - self.queueProcessTimeout
                )
                overdueItems = (yield itemType.query(
                    txn, (itemType.notBefore < tooLate))
                )
                for overdueItem in overdueItems:
                    peer = self.choosePerformer()
                    yield peer.performWork(overdueItem.table,
                                           overdueItem.workID)

        if not self.running:
            return succeed(None)

        return inTransaction(self.transactionFactory, workCheck)

    _currentWorkDeferred = None
    _lostWorkCheckCall = None

    def _lostWorkCheckLoop(self):
        """
        While the service is running, keep checking for any overdue / lost work
        items and re-submit them to the cluster for processing.  Space out
        those checks in time based on the size of the cluster.
        """
        self._lostWorkCheckCall = None

        if not self.running:
            return

        @passthru(
            self._periodicLostWorkCheck().addErrback(log.err).addCallback
        )
        def scheduleNext(result):
            self._currentWorkDeferred = None
            if not self.running:
                return
            index = self.nodeIndex()
            now = self.reactor.seconds()

            interval = self.queueDelayedProcessInterval
            count = self.totalNumberOfNodes()
            when = (now - (now % interval)) + (interval * (count + index))
            delay = when - now
            self._lostWorkCheckCall = self.reactor.callLater(
                delay, self._lostWorkCheckLoop
            )

        self._currentWorkDeferred = scheduleNext


    def startService(self):
        """
        Register ourselves with the database and establish all outgoing
        connections to other servers in the cluster.
        """
        @inlineCallbacks
        def startup(txn):
            endpoint = TCP4ServerEndpoint(self.reactor, self.ampPort)
            # If this fails, the failure mode is going to be ugly, just like
            # all conflicted-port failures.  But, at least it won't proceed.
            self._listeningPort = yield endpoint.listen(self.peerFactory())
            self.ampPort = self._listeningPort.getHost().port
            yield Lock.exclusive(NodeInfo.table).on(txn)
            nodes = yield self.activeNodes(txn)
            selves = [node for node in nodes
                      if ((node.hostname == self.hostname) and
                          (node.port == self.ampPort))]
            if selves:
                self.thisProcess = selves[0]
                nodes.remove(self.thisProcess)
                yield self.thisProcess.update(pid=self.pid,
                                              time=datetime.now())
            else:
                self.thisProcess = yield NodeInfo.create(
                    txn, hostname=self.hostname, port=self.ampPort,
                    pid=self.pid, time=datetime.now()
                )

            for node in nodes:
                self._startConnectingTo(node)

        self._startingUp = inTransaction(self.transactionFactory, startup)

        @self._startingUp.addBoth
        def done(result):
            self._startingUp = None
            super(PeerConnectionPool, self).startService()
            self._lostWorkCheckLoop()
            return result


    @inlineCallbacks
    def stopService(self):
        """
        Stop this service, terminating any incoming or outgoing connections.
        """
        # If in the process of starting up, always wait for startup to complete before
        # stopping,.
        if self._startingUp is not None:
            d = Deferred()
            self._startingUp.addBoth(lambda result: d.callback(None))
            yield d

        yield super(PeerConnectionPool, self).stopService()

        if self._listeningPort is not None:
            yield self._listeningPort.stopListening()

        if self._lostWorkCheckCall is not None:
            self._lostWorkCheckCall.cancel()

        if self._currentWorkDeferred is not None:
            self._currentWorkDeferred.cancel()

        for connector in self._connectingToPeer:
            d = Deferred()
            connector.addBoth(lambda result: d.callback(None))
            yield d

        for peer in self.peers:
            peer.transport.abortConnection()


    def activeNodes(self, txn):
        """
        Load information about all other nodes.
        """
        return NodeInfo.all(txn)


    def mapPeer(self, host, port, peer):
        """
        A peer has been identified as belonging to the given host/port
        combination.  Disconnect any other peer that claims to be connected for
        the same peer.
        """
        # if (host, port) in self.mappedPeers:
        #     TODO: think about this for race conditions
        #     self.mappedPeers.pop((host, port)).transport.loseConnection()
        self.mappedPeers[(host, port)] = peer

    _connectingToPeer = []

    def _startConnectingTo(self, node):
        """
        Start an outgoing connection to another master process.

        @param node: a description of the master to connect to.
        @type node: L{NodeInfo}
        """
        connected = node.endpoint(self.reactor).connect(self.peerFactory())
        self._connectingToPeer.append(connected)

        def whenConnected(proto):
            self._connectingToPeer.remove(connected)
            self.mapPeer(node.hostname, node.port, proto)
            proto.callRemote(
                IdentifyNode,
                host=self.thisProcess.hostname,
                port=self.thisProcess.port
            ).addErrback(noted, "identify")

        def noted(err, x="connect"):
            if x == "connect":
                self._connectingToPeer.remove(connected)
            log.msg(
                "Could not {0} to cluster peer {1} because {2}"
                .format(x, node, str(err.value))
            )

        connected.addCallbacks(whenConnected, noted)


    def peerFactory(self):
        """
        Factory for peer connections.

        @return: a L{Factory} that will produce L{ConnectionFromPeerNode}
            protocols attached to this L{PeerConnectionPool}.
        """
        return _PeerPoolFactory(self)



class _PeerPoolFactory(Factory, object):
    """
    Protocol factory responsible for creating L{ConnectionFromPeerNode}
    connections, both client and server.
    """

    def __init__(self, peerConnectionPool):
        self.peerConnectionPool = peerConnectionPool


    def buildProtocol(self, addr):
        return ConnectionFromPeerNode(self.peerConnectionPool)



class LocalQueuer(_BaseQueuer):
    """
    When work is enqueued with this queuer, it is just executed locally.
    """
    implements(IQueuer)

    def __init__(self, txnFactory, reactor=None):
        super(LocalQueuer, self).__init__()
        self.txnFactory = txnFactory
        if reactor is None:
            from twisted.internet import reactor
        self.reactor = reactor


    def choosePerformer(self):
        """
        Choose to perform the work locally.
        """
        return LocalPerformer(self.txnFactory)



class NonPerformer(object):
    """
    Implementor of C{performWork} that doesn't actual perform any work.  This
    is used in the case where you want to be able to enqueue work for someone
    else to do, but not take on any work yourself (such as a command line
    tool).
    """
    implements(_IWorkPerformer)

    def performWork(self, table, workID):
        """
        Don't perform work.
        """
        return succeed(None)



class NonPerformingQueuer(_BaseQueuer):
    """
    When work is enqueued with this queuer, it is never executed locally.
    It's expected that the polling machinery will find the work and perform it.
    """
    implements(IQueuer)

    def __init__(self, reactor=None):
        super(NonPerformingQueuer, self).__init__()
        if reactor is None:
            from twisted.internet import reactor
        self.reactor = reactor


    def choosePerformer(self):
        """
        Choose to perform the work locally.
        """
        return NonPerformer()
