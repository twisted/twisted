twisted.enterprise has been ported to Python 3.
The third-party pysqlite2 package has not been ported to Python 3,
so any database connector based on pysqlite2 cannot be used.
Instead the sqlite3 module included with Python 3 should be used.
