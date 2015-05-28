# -*- test-case-name: twext.enterprise.test.test_locking -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Utilities to restrict concurrency based on mutual exclusion.
"""

from twext.enterprise.dal.model import Table
from twext.enterprise.dal.model import SQLType
from twext.enterprise.dal.model import Constraint
from twext.enterprise.dal.syntax import SchemaSyntax
from twext.enterprise.dal.model import Schema
from twext.enterprise.dal.record import Record
from twext.enterprise.dal.record import fromTable


class AlreadyUnlocked(Exception):
    """
    The lock you were trying to unlock was already unlocked.
    """



class LockTimeout(Exception):
    """
    The lock you were trying to lock was already locked causing a timeout.
    """



def makeLockSchema(inSchema):
    """
    Create a self-contained schema just for L{Locker} use, in C{inSchema}.

    @param inSchema: a L{Schema} to add the locks table to.
    @type inSchema: L{Schema}

    @return: inSchema
    """
    LockTable = Table(inSchema, "NAMED_LOCK")

    LockTable.addColumn("LOCK_NAME", SQLType("varchar", 255))
    LockTable.tableConstraint(Constraint.NOT_NULL, ["LOCK_NAME"])
    LockTable.tableConstraint(Constraint.UNIQUE, ["LOCK_NAME"])
    LockTable.primaryKey = [LockTable.columnNamed("LOCK_NAME")]

    return inSchema

LockSchema = SchemaSyntax(makeLockSchema(Schema(__file__)))



class NamedLock(Record, fromTable(LockSchema.NAMED_LOCK)):
    """
    An L{AcquiredLock} lock against a shared data store that the current
    process holds via the referenced transaction.
    """

    @classmethod
    def acquire(cls, txn, name):
        """
        Acquire a lock with the given name.

        @param name: The name of the lock to acquire.  Against the same store,
            no two locks may be acquired.
        @type name: L{unicode}

        @return: a L{Deferred} that fires with an L{AcquiredLock} when the lock
            has fired, or fails when the lock has not been acquired.
        """
        def autoRelease(self):
            txn.preCommit(lambda: self.release(True))
            return self

        def lockFailed(f):
            raise LockTimeout(name)

        d = cls.create(txn, lockName=name)
        d.addCallback(autoRelease)
        d.addErrback(lockFailed)
        return d


    def release(self, ignoreAlreadyUnlocked=False):
        """
        Release this lock.

        @param ignoreAlreadyUnlocked: If you don't care about the current
            status of this lock, and just want to release it if it is still
            acquired, pass this parameter as L{True}.  Otherwise this method
            will raise an exception if it is invoked when the lock has already
            been released.

        @raise: L{AlreadyUnlocked}

        @return: A L{Deferred} that fires with L{None} when the lock has been
            unlocked.
        """
        return self.delete()
