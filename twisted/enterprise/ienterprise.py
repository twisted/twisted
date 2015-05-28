# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Interfaces, mostly related to L{twext.enterprise.adbapi2}.
"""

__all__ = [
    "IAsyncTransaction",
    "ISQLExecutor",
    "ICommandBlock",
    "IQueuer",
    "IDerivedParameter",
    "AlreadyFinishedError",
    "ConnectionError",
    "POSTGRES_DIALECT",
    "SQLITE_DIALECT",
    "ORACLE_DIALECT",
    "ORACLE_TABLE_NAME_MAX",
]

from zope.interface import Interface, Attribute


class AlreadyFinishedError(Exception):
    """
    The transaction was already completed via an C{abort} or C{commit} and
    cannot be aborted or committed again.
    """



class ConnectionError(Exception):
    """
    An error occurred with the underlying database connection.
    """



POSTGRES_DIALECT = "postgres-dialect"
ORACLE_DIALECT = "oracle-dialect"
SQLITE_DIALECT = "sqlite-dialect"
ORACLE_TABLE_NAME_MAX = 30



class ISQLExecutor(Interface):
    """
    Base SQL-execution interface, for a group of commands or a transaction.
    """

    paramstyle = Attribute(
        """
        A copy of the C{paramstyle} attribute from a DB-API 2.0 module.
        """
    )

    dialect = Attribute(
        """
        A copy of the C{dialect} attribute from the connection pool.  One of
        the C{*_DIALECT} constants in this module, such as L{POSTGRES_DIALECT}.
        """
    )


    def execSQL(sql, args=(), raiseOnZeroRowCount=None):
        """
        Execute some SQL.

        @param sql: an SQL string.

        @type sql: C{str}

        @param args: C{list} of arguments to interpolate into C{sql}.

        @param raiseOnZeroRowCount: a 0-argument callable which returns an
            exception to raise if the executed SQL does not affect any rows.

        @return: L{Deferred} which fires C{list} of C{tuple}

        @raise: C{raiseOnZeroRowCount} if it was specified and no rows were
            affected.
        """



class IAsyncTransaction(ISQLExecutor):
    """
    Asynchronous execution of SQL.

    Note that there is no C{begin()} method; if an L{IAsyncTransaction} exists
    at all, it is assumed to have been started.
    """

    def commit():
        """
        Commit changes caused by this transaction.

        @return: L{Deferred} which fires with C{None} upon successful
            completion of this transaction, or fails if this transaction could
            not be committed.  It fails with L{AlreadyFinishedError} if the
            transaction has already been committed or rolled back.
        """

    def preCommit(operation):
        """
        Perform the given operation when this L{IAsyncTransaction}'s C{commit}
        method is called, but before the underlying transaction commits.  If
        any exception is raised by this operation, underlying database commit
        will be blocked and rollback run instead.

        @param operation: a 0-argument callable that may return a L{Deferred}.
            If it does, then the subsequent operations added by L{postCommit}
            will not fire until that L{Deferred} fires.
        """

    def postCommit(operation):
        """
        Perform the given operation only after this L{IAsyncTransaction}
        commits.  These will be invoked before the L{Deferred} returned by
        L{IAsyncTransaction.commit} fires.

        @param operation: a 0-argument callable that may return a L{Deferred}.
            If it does, then the subsequent operations added by L{postCommit}
            will not fire until that L{Deferred} fires.
        """

    def abort():
        """
        Roll back changes caused by this transaction.

        @return: L{Deferred} which fires with C{None} upon successful
            rollback of this transaction.
        """

    def postAbort(operation):
        """
        Invoke a callback after abort.

        @see: L{IAsyncTransaction.postCommit}

        @param operation: 0-argument callable, potentially returning a
            L{Deferred}.
        """

    def commandBlock():
        """
        Create an object which will cause the commands executed on it to be
        grouped together.

        This is useful when using database-specific features such as
        sub-transactions where order of execution is importnat, but where
        application code may need to perform I/O to determine what SQL,
        exactly, it wants to execute.  Consider this fairly contrived example
        for an imaginary database::

            def storeWebPage(url, block):
                block.execSQL("BEGIN SUB TRANSACTION")
                got = getPage(url)
                def gotPage(data):
                    block.execSQL("INSERT INTO PAGES (TEXT) VALUES (?)",
                                  [data])
                    block.execSQL("INSERT INTO INDEX (TOKENS) VALUES (?)",
                                  [tokenize(data)])
                    lastStmt = block.execSQL("END SUB TRANSACTION")
                    block.end()
                    return lastStmt
                return got.addCallback(gotPage)
            gatherResults([storeWebPage(url, txn.commandBlock())
                          for url in urls]).addCallbacks(
                            lambda x: txn.commit(), lambda f: txn.abort()
                          )

        This fires off all the C{getPage} requests in parallel, and prepares
        all the necessary SQL immediately as the results arrive, but executes
        those statements in order.  In the above example, this makes sure to
        store the page and its tokens together, another use for this might be
        to store a computed aggregate (such as a sum) at a particular point in
        a transaction, without sacrificing parallelism.

        @rtype: L{ICommandBlock}
        """



class ICommandBlock(ISQLExecutor):
    """
    This is a block of SQL commands that are grouped together.

    @see: L{IAsyncTransaction.commandBlock}
    """

    def end():
        """
        End this command block, allowing other commands queued on the
        underlying transaction to end.

        @note: This is I{not} the same as either L{IAsyncTransaction.commit} or
            L{IAsyncTransaction.abort}, since it does not denote success or
            failure; merely that the command block has completed and other
            statements may now be executed.  Since sub-transactions are a
            database-specific feature, they must be implemented at a
            higher-level than this facility provides (although this facility
            may be useful in their implementation).  Also note that, unlike
            either of those methods, this does I{not} return a Deferred: if you
            want to know when the block has completed, simply add a callback to
            the last L{ICommandBlock.execSQL} call executed on this
            L{ICommandBlock}.  (This may be changed in a future version for the
            sake of convenience, however.)
        """



class IDerivedParameter(Interface):
    """
    A parameter which needs to be derived from the underlying DB-API cursor;
    implicitly, meaning that this must also interact with the actual thread
    manipulating said cursor.  If a provider of this interface is passed in the
    C{args} argument to L{IAsyncTransaction.execSQL}, it will have its
    C{prequery} and C{postquery} methods invoked on it before and after
    executing the SQL query in question, respectively.

    @note: L{IDerivedParameter} providers must also always be I{pickleable},
        because in some cases the actual database cursor objects will be on the
        other end of a network connection.  For an explanation of why this
        might be, see L{twext.enterprise.adbapi2.ConnectionPoolConnection}.
    """

    def preQuery(cursor):
        """
        Before running a query, invoke this method with the cursor that the
        query will be run on.

        (This can be used, for example, to allocate a special database-specific
        variable based on the cursor, like an out parameter.)

        @param cursor: the DB-API cursor.

        @return: the concrete value which should be passed to the DB-API layer.
        """

    def postQuery(cursor):
        """
        After running a query, invoke this method in the DB-API thread.

        (This can be used, for example, to manipulate any state created in the
        preQuery method.)

        @param cursor: the DB-API cursor.

        @return: C{None}
        """



class IQueuer(Interface):
    """
    An L{IQueuer} can enqueue work for later execution.
    """

    def enqueueWork(self, transaction, workItemType, **kw):
        """
        Perform some work, eventually.

        @param transaction: an L{IAsyncTransaction} within which to I{commit}
            to doing the work.  Note that this work will likely be done later
            (but depending on various factors, may actually be done within this
            transaction as well).

        @param workItemType: the type of work item to create.
        @type workItemType: L{type}, specifically, a subtype of L{WorkItem
            <twext.enterprise.jobqueue.WorkItem>}

        @param kw: The keyword parameters are relayed to C{workItemType.create}
            to create an appropriately initialized item.

        @return: a work proposal that allows tracking of the various phases of
            completion of the work item.
        @rtype: L{twext.enterprise.jobqueue.WorkItem}
        """

    def callWithNewProposals(self, callback):
        """
        Tells the IQueuer to call a callback method whenever a new WorkProposal
        is created.

        @param callback: a callable which accepts a single parameter, a
            L{WorkProposal}
        """

    def transferProposalCallbacks(self, newQueuer):
        """
        Transfer the registered callbacks to the new queuer.
        """
