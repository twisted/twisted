
"""Posting board that uses a relation database to store msgs.
"""



from twisted.spread import pb
from twisted.enterprise import adbapi

from pyPgSQL import PgSQL

import gadgets
import manager

class ForumService(pb.Service):

    def __init__(self, name, app, dbpool):
        pb.Service.__init__(self, name, app)
        self.dbpool = dbpool
        self.manager = manager.ForumManager(dbpool)
        

