
"""Posting board that uses a relation database to store msgs.
"""



from twisted.spread import pb
from twisted.enterprise import adbapi

from pyPgSQL import PgSQL

import gadgets
import manager

class ForumUser(pb.Perspective):
    def __init__(self, identity_name, user_name, sig):
        pb.Perspective.__init__(self, identity_name, user_name)
        self.signature = sig

class ForumService(pb.Service):

    def __init__(self, name, app, dbpool, desc ):
        pb.Service.__init__(self, name, app)
        self.dbpool = dbpool
        self.manager = manager.ForumDB(dbpool)
        self.desc = desc

        
    def getPerspectiveRequest(self, name):
        return self.manager.getPerspectiveRequest(name)

