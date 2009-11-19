# Copyright (c) 2009 Twisted Matrix Laboratories.
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
        pass


    def cursor(self):
        return Cursor(self)


    def commit(self):
        pass


    def close(self):
        pass



class Cursor(object):
    """
    A mock DB-API 2.0 Cursor class.
    """

    # track arraysize attribute by passed in 'sizeId' attribute on cursor
    __sizes = {}

    def __init__(self, conn):
        self.conn = conn


    def execute(self, sql, *args, **kwargs):
        """
        Track the arraysize attribute of the cursor.
        """

        try:
            self.__sizes[kwargs.pop('sizeId')] = self.arraysize
        except:
            pass
        return None


    def fetchall(self):
        return [[1]]


    def close(self):
        pass


    def getArraysize(self, sizeId):
        """
        Return the arraysize attribute of the cursor that was executed
        with this sizeId.
        """

        return self.__sizes.get(sizeId)



def connect(*args, **kwargs):
    return Connection(*args, **kwargs)
