#!/usr/bin/env python2.3

import pg
import pdb
import sys
import interfaces
from twisted.python import components
from cStringIO import StringIO
from Category import Category
from Bookmark import Bookmark
from BookmarkContainer import BookmarkContainer
from PageData import PageData

TRACE = False

class RDBStorage:
    DBNAME = 'bookmarks'
    __implements__ = (interfaces.IDataStore,)
    def __init__(self):
        pass

    def _get_cnx(self):
        return pg.DB(dbname=self.DBNAME)

    def get_EditPageData(self):
        '''returns a BookmarkContainer that contains all bookmarks'''
        bookmark_list = self.get_Bookmarks()
        return BookmarkContainer(bookmark_list)

    def get_PageData(self, page_url='/home'):
        cat_list = self._get_Category_list_for_page(page_url)
        return PageData(categories=cat_list, page_url=page_url)

    def _get_Category_list_for_page(self, page_url='/home'):
        cnx = self._get_cnx()
        cat_name_list = self._get_category_names(page_url=page_url)
        cat_list = []
        for cat_name in cat_name_list:
            bookmark_list = self.get_Bookmarks(category=cat_name)
            cat_list.append(Category(bookmarks=bookmark_list, 
                            page_url=page_url, name=cat_name))
        return cat_list

    def _get_category_names(self, page_url='/home'):
        cnx = self._get_cnx()
        qstr = """
    SELECT DISTINCT b.category 
      FROM bookmark b 
     WHERE b.page_url = '%s';
""" % page_url

        result = cnx.query(qstr).getresult()
        return [r[0] for r in result]
 
    def get_MenuData(self):
        cnx = self._get_cnx()
        rows = cnx.query('SELECT m.name, m.page_url FROM menu m;').dictresult()
        bmarks = [Bookmark(**row) for row in rows]
        return BookmarkContainer(bookmarks=bmarks)

    def delete_Bookmark(self, bookmark):
        qstr = "DELETE FROM bookmark where id = %s;" % bookmark.id
        cnx = self._get_cnx()
        cnx.query(qstr)

    def get_Category_combobox_data(self, page_url='/home'):
        return self._get_category_names(page_url)

    def update_Bookmark(self, bookmark):
        qstr = """
     UPDATE bookmark       
        SET page_url = '%s',
            category = '%s',
                name = '%s',
                 url = '%s'
      WHERE       id =  %s
    """ % (bookmark.page_url, 
           bookmark.category, 
           bookmark.name, 
           bookmark.url, 
           bookmark.id)
        cnx = self._get_cnx()
        cnx.query(qstr)

    def add_Bookmark(self,bookmark):
        print 'add_Bookmark called'
        cnx = self._get_cnx()
        qobj = cnx.query("SELECT nextval('bookmark_id_seq');").dictresult()
        id = qobj[0]['nextval']
        qstr = """
    INSERT INTO bookmark (id, page_url, category, name, url) 
                  values (%s,'%s','%s','%s','%s');""" % (id, bookmark.page_url, bookmark.category, bookmark.name, bookmark.url) 
        
        cnx.query(qstr)
        bookmark.id = id


    def get_Bookmarks(self,**kwargs):
        '''returns a list of Bookmark instances with attributes specified
if **kwargs does not contain any arguments, returns all bookmarks in database
    '''
        TRACE = False
        cnx = self._get_cnx()
        sio = StringIO()
        sio.write("""SELECT b.id, b.category, b.name, b.url, b.page_url 
                    FROM bookmark b
    """)

        # check for at least 1 kwarg
        num_kwargs = len(kwargs.keys())
        if num_kwargs > 0:
            sio.write("WHERE")
            count = 0
            the_and = ""
            for kw in ['id', 'url', 'name', 'page_url', 'category']:
                if kw in kwargs:
                    if count > 0:
                        the_and = "AND"
                    sio.writelines([the_and, " b.%s = '%s'\n" % (kw, kwargs[kw])])
                    count += 1
        sio.write(';')
        qstr = sio.getvalue()
        if TRACE:
            print qstr
        rows = cnx.query(qstr).dictresult()
        if not rows:
            return None
        if len(rows) > 1:
            return [Bookmark(**row) for row in rows]
        return Bookmark(**rows[0])
    

    def get_Bookmarks_with_attr(self,**kwargs):
        '''syntactic sugar (until i clean up the rest of the code not to use this)'''
        return self.get_Bookmarks(**kwargs)

