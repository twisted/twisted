#!/usr/bin/env python2.3

import pg
DBNAME = 'bookmarks'
TRACE = False
import pdb
import Bookmark

class Error(Exception):
    pass

class IllegalNumArgumentsError(Error):
    def __init__(self, message):
        self.message = message

def get_cnx():
    if TRACE:
        print 'get_cnx'
    return pg.DB(dbname=DBNAME)

def get_categories(page_url='/docs'):
    if TRACE:
        print 'get_categories'
    cnx = get_cnx()
    result = cnx.query('SELECT DISTINCT b.category FROM bookmark b ' +
            "WHERE b.page_url = '" + page_url + "';").getresult()
    return [r[0] for r in result]
    
def get_links(page_url='/docs', category=None):
    if TRACE:
        print 'get_links'
    cnx = get_cnx()
    qstr = ''.join(['SELECT b.id, b.category, b.name, b.url, b.page_url ',
            'FROM bookmark b ',
            "WHERE b.page_url = '", page_url, "' "])
    if category:
        qstr = ''.join([qstr, "AND b.category = '", category, "';"])
    else:
        qstr = ''.join([qstr, ';'])
    return cnx.query(qstr)

def get_MenuData():
    if TRACE:
        print 'get_MenuData'
    cnx = get_cnx()
    return cnx.query('SELECT m.name, m.page_url FROM menu m;').dictresult()

def get_menu_class():
    rows = get_MenuData()
    return [Bookmark.Bookmark(synced=True, **row) for row in rows]

def delete_Bookmark(bookmark):
    qstr = "DELETE FROM bookmark where id = %s;" % bookmark.id
    cnx = get_cnx()
    cnx.query(qstr)

def update_Bookmark(bookmark):
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

    cnx = get_cnx()
    cnx.query(qstr)

def add_Bookmark(bookmark):
#   '''adds a bookmark object to the database and returns the 
#automatically inserted id value '''
    cnx = get_cnx()
    qobj = cnx.query("SELECT nextval('bookmark_id_seq');").dictresult()
    id = qobj[0]['nextval']
    qstr = """
INSERT INTO bookmark (id, page_url, category, name, url) 
              values (%s,'%s','%s','%s','%s');""" % (id, bookmark.page_url, bookmark.category, bookmark.name, bookmark.url) 
    
    cnx.query(qstr)
    bookmark._set_id(id)

def get_Bookmarks(page_url='/docs', category=None):
    '''this is deprecated and will change as soon 
as i finish updating the woven portion of this program'''
    rows = get_links(page_url=page_url, category=category).dictresult()
    return [Bookmark.Bookmark(synced=True, **row) for row in rows]

def get_Bookmarks_with_attr(**kwargs):
    '''returns a bookmark instance with attribute specified
**kwargs must contain one of [id, url, name, page_url, category] 
'''
    cnx = get_cnx()
    qstr = """SELECT b.id, b.category, b.name, b.url, b.page_url 
                FROM bookmark b
               WHERE
"""
    # check for at least 1 kwarg
    num_kwargs = len(kwargs.keys())
    if num_kwargs < 1:
        raise IllegalNumArgumentsError("num kwargs must be > 1")
    
    count = 0
    the_and = ""
    for kw in ['id', 'url', 'name', 'page_url', 'category']:
        if kw in kwargs:
            if count > 0:
                the_and = "AND"
            qstr = ''.join([qstr, the_and, " b.%s = '%s'\n" % (kw, kwargs[kw])])
            count += 1
    qstr = ''.join([qstr, ';'])
    print qstr
    rows = cnx.query(qstr).dictresult()
    if not rows:
        return None
    return [Bookmark.Bookmark(synced=True, **row) for row in rows]

