#!/usr/bin/env python2.3 

from bsddb import dbshelve

class BSDStorage:
    dbname = 'bookmarks.db'
    def __init__(self):
        self.db = dbshelve.open(self.dbname)
        
        
