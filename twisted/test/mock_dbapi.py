# Copyright (c) 2009-2010 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This is a mock dbapi.

The purpose of this module is to mock a DB-API 2.0 compatible module in order
to track the arraysize attribute of a cursor.  It is suitable to be referenced
by the dbapiName parameter of an adbapi.ConnectionPool.
"""

class Connection(object):
    """
    A mock DB-API 2.0 Connection class.
    """

    def __init__(self, *args, **kwargs):
        self._sizes = {}


    def cursor(self):
        return Cursor(self)


    def commit(self):
        pass


    def close(self):
        pass


    def getArraysize(self, sizeId):
        """
        Return the arraysize attribute of the cursor that was executed
        with this sizeId.
        """

        return self._sizes.get(sizeId)



class Cursor(object):
    """
    A mock DB-API 2.0 Cursor class.

    @ivar _connection: A reference to the L{Connection} which created the
        cursor, used to keep track of arraysizes.
    """

    def __init__(self, connection):
        self._connection = connection
        self.arraysize = 1 # default as required by DBAPI


    def execute(self, sql, *args, **kwargs):
        """
        Track the arraysize attribute of the cursor.
        """
        try:
            sizeId = kwargs.pop('sizeId')
        except KeyError:
            pass
        else:
            self._connection._sizes[sizeId] = self.arraysize


    def fetchall(self):
        return [[1]]


    def close(self):
        pass



def connect(*args, **kwargs):
    return Connection(*args, **kwargs)
