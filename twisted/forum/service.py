
"""Posting board that uses a relation database to store msgs.
"""



from twisted.spread import pb
from twisted.enterprise import adbapi

from pyPgSQL import PgSQL

import gadgets

class ForumService(pb.Service):

    def __init__(self, name, app, dbhost, dbport):
        pb.Service.__init__(self, name, app)
        self.dbhost = dbhost
        self.dbport = dbport
        connectString = "%s:%d" % (dbhost, dbport)
        self.pool = adbapi.ConnectionPool(PgSQL, connectString)
        self.pool.connect()

        
        
                                       
        
