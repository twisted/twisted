#!/usr/bin/env python2.3

import pdb
from BookmarkContainer import BookmarkContainer
from storage.RDBStorage import RDBStorage
dbcnx = RDBStorage()

class MenuData(BookmarkContainer):
    '''a data type understood by the woven view to render the menu'''
    def __init__(self):
        BookmarkContainer.__init__(self)
        self._load_menu_items()
        
    def _load_menu_items(self):
        self.extend(dbcnx.get_menu_class())


