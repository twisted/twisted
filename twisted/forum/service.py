
"""Posting board that uses a relation database to store msgs.
"""



from twisted.spread import pb
from twisted.enterprise import adbapi

from pyPgSQL import PgSQL

import gadgets

class ForumService(pb.Service):

    def __init__(self, name, app, dbpool):
        pb.Service.__init__(self, name, app)
        self.pool = dbpool# adbapi.ConnectionPool(PgSQL, connectString)
        self.pool.connect()

