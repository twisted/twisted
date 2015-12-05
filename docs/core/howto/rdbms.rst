
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

twisted.enterprise.adbapi: Twisted RDBMS support
================================================

Abstract
--------

Twisted is an asynchronous networking framework, but most database API implementations unfortunately have blocking interfaces -- for this reason, :api:`twisted.enterprise.adbapi <twisted.enterprise.adbapi>` was created.
It is a non-blocking interface to the standardized DB-API 2.0 API, which allows you to access a number of different RDBMSes.


What you should already know
----------------------------

- Python :-)
- How to write a simple Twisted Server (see :doc:`this tutorial <servers>` to learn how)
- Familiarity with using database interfaces (see `the documentation for DBAPI 2.0 <http://www.python.org/dev/peps/pep-0249/>`_)


Quick Overview
--------------

Twisted is an asynchronous framework.
This means standard database modules cannot be used directly, as they typically work something like::

    # Create connection...
    db = dbmodule.connect('mydb', 'andrew', 'password')
    # ...which blocks for an unknown amount of time

    # Create a cursor
    cursor = db.cursor()

    # Do a query...
    resultset = cursor.query('SELECT * FROM table WHERE ...')
    # ...which could take a long time, perhaps even minutes.

Those delays are unacceptable when using an asynchronous framework such as Twisted.
For this reason, Twisted provides :api:`twisted.enterprise.adbapi <twisted.enterprise.adbapi>`, an asynchronous wrapper for any `DB-API 2.0 <http://www.python.org/dev/peps/pep-0249/>`_-compliant module.

:api:`twisted.enterprise.adbapi <adbapi>` will do blocking database operations in separate threads, which trigger callbacks in the originating thread when they complete.
In the meantime, the original thread can continue doing normal work, like servicing other requests.


How do I use adbapi?
--------------------

Rather than creating a database connection directly, use the :api:`twisted.enterprise.adbapi.ConnectionPool <adbapi.ConnectionPool>` class to manage a connections for you.
This allows :api:`twisted.enterprise.adbapi <adbapi>` to use multiple connections, one per thread. This is easy::

    # Using the "dbmodule" from the previous example, create a ConnectionPool
    from twisted.enterprise import adbapi
    dbpool = adbapi.ConnectionPool("dbmodule", 'mydb', 'andrew', 'password')

Things to note about doing this:

- There is no need to import dbmodule directly.
  You just pass the name to :api:`twisted.enterprise.adbapi.ConnectionPool <adbapi.ConnectionPool>`'s constructor.
- The parameters you would pass to dbmodule.connect are passed as extra arguments to :api:`twisted.enterprise.adbapi.ConnectionPool <adbapi.ConnectionPool>`'s constructor.
  Keyword parameters work as well.

Now we can do a database query::

    # equivalent of cursor.execute(statement), return cursor.fetchall():
    def getAge(user):
        return dbpool.runQuery("SELECT age FROM users WHERE name = ?", user)

    def printResult(l):
        if l:
            print l[0][0], "years old"
        else:
            print "No such user"

    getAge("joe").addCallback(printResult)

This is straightforward, except perhaps for the return value of ``getAge``.
It returns a :api:`twisted.internet.defer.Deferred <Deferred>`, which allows arbitrary callbacks to be called upon completion (or upon failure).
More documentation on Deferred is available :doc:`here <defer>`.


In addition to ``runQuery``, there is also ``runOperation`` and ``runInteraction`` that gets called with a callable (e.g. a function).
The function will be called in the thread with a :api:`twisted.enterprise.adbapi.Transaction <adbapi.Transaction>`, which basically mimics a DB-API cursor.
In all cases a database transaction will be committed after your database usage is finished, unless an exception is raised in which case it will be rolled back.

.. code-block:: python

    def _getAge(txn, user):
        # this will run in a thread, we can use blocking calls
        txn.execute("SELECT * FROM foo")
        # ... other cursor commands called on txn ...
        txn.execute("SELECT age FROM users WHERE name = ?", user)
        result = txn.fetchall()
        if result:
            return result[0][0]
        else:
            return None

    def getAge(user):
        return dbpool.runInteraction(_getAge, user)

    def printResult(age):
        if age != None:
            print age, "years old"
        else:
            print "No such user"

    getAge("joe").addCallback(printResult)

Also worth noting is that these examples assumes that dbmodule uses the "qmarks" paramstyle (see the DB-API specification).
If your dbmodule uses a different paramstyle (e.g. pyformat) then use that.
Twisted doesn't attempt to offer any sort of magic parameter munging -- ``runQuery(query, params, ...)`` maps directly onto ``cursor.execute(query, params, ...)``.


Examples of various database adapters
-------------------------------------

Notice that the first argument is the module name you would usually import and get ``connect(...)`` from, and that following arguments are whatever arguments you'd call ``connect(...)`` with.

.. code-block:: python

    from twisted.enterprise import adbapi

    # PostgreSQL PyPgSQL
    cp = adbapi.ConnectionPool("pyPgSQL.PgSQL", database="test")

    # MySQL
    cp = adbapi.ConnectionPool("MySQLdb", db="test")


And that's it!
--------------

That's all you need to know to use a database from within Twisted.
You probably should read the adbapi module's documentation to get an idea of the other functions it has, but hopefully this document presents the core ideas.
