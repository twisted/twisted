import pdb

from BookmarkContainer import BookmarkContainer
from storage.RDBStorage import RDBStorage
dbcnx = RDBStorage()

class EditPageData(BookmarkContainer):
    page_url = '/home'
    name = None
    def __init__(self):
        BookmarkContainer.__init__(self)


