#!/usr/bin/env python2.3

import pdb
from cStringIO import StringIO
from BookmarkContainer import BookmarkContainer

class Error(Exception):
    pass

class BookmarkNotInCategoryError(Error):
    def __init__(self, message):
        self.message = message

class Category(BookmarkContainer):
    def __init__(self, bookmarks=[], page_url='', name=''):
        BookmarkContainer.__init__(self)
        self.bookmarks = bookmarks
        self.page_url = page_url
        self._name = name
        self._reindex()

# --- Property definition ---

    def _get_name(self):
        return self._name
    def _set_name(self, val):
        self._name = val
#       TODO: add category changing code 
    name = property(_get_name, _set_name)

    def __str__(self):
        sio = StringIO()
        sio.write("Category \n\tname: %s\n" % self.name)
        sio.write("\tpage_url: %s\n" % self.page_url)
        sio.write("\tBookmarks:\n")
        for bm in self.bookmarks:
            sio.write("\t\t%s, %s\n" % (bm.name, bm.url))
        sio.write("------")
        return sio.getvalue()

    def locate_Bookmark(self, id=None, name=None, url=None):
        '''returns bookmark with attribute matching id, name, and url
example: to find a bookmark where boomark.id = 42 
         _locate_Bookmark(id=42)
'''
        for bm in self:
            if id:
                if bm.id == id:
                    return bm
            if name:
                if bm.name == name:
                    return bm
            if url:
                if bm.url == url:
                    return bm
        raise BookmarkNotInCategoryError, 'bookmark not found' 

