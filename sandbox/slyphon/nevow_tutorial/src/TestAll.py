#!/usr/bin/env python2.3

import pg
import pdb
import unittest

from Category import Category
from PageData import PageData
from storage.CSVStorage import CSVStorage
from Bookmark import Bookmark

from storage.RDBStorage import RDBStorage

class BookmarksTC(unittest.TestCase):
    def setUp(self):
        self.test_bm = {'id': None, 
                    'page_url': '/home', 
                    'category': 'Links', 
                    'name': 'example', 
                    'url': 'http://www.example.net' }
        self.bm = Bookmark(**self.test_bm)
        self.cat_names_list = ['Admin', 'Docs', 'Java', 'Links', 'Struts', 'Twisted Servers']
        self.csv = CSVStorage(prepath="storage/")

        self.testpage = '/home'
        self.dbcnx = RDBStorage()
 
    def tearDown(self):
        try:
            cnx = self.dbcnx._get_cnx()
            cnx.query("DELETE from bookmark where name LIKE '%example%';")
            self.csv.remove(self.bm)
        except Exception, e:
            pass

# --= Category Tests =--

class TestCategory(BookmarksTC):
    def testCategory_id_dict(self):
        catlist = self.dbcnx._get_Category_list_for_page(page_url=self.testpage)
        for cat in catlist:
            for bm in cat.bookmarks:
                cat.locate_Bookmark(id=bm.id)


# --= Menu Tests =--

#class TestMenu(BookmarksTC):
#


# --= RDBStorage Tests =--

class Test_RDBStorage(BookmarksTC):
    def test_get_PageData(self):
        pagedata = self.dbcnx.get_PageData(self.testpage)
        self.assert_(isinstance(pagedata, PageData))
        for cat in pagedata.categories:
            self.assert_(isinstance(cat, Category))
            self.assert_(cat.bookmarks)
    
    def test_get_Category_list_for_page(self):
        cat_names_list = self.dbcnx._get_Category_list_for_page(self.testpage)
        for cat in cat_names_list:
            self.assert_(isinstance(cat, Category))
            self.assert_(cat.bookmarks)
    
    def test_get_category_names(self):
        cat_names = self.dbcnx._get_category_names(self.testpage)
        self.assertEqual(len(cat_names), len(self.cat_names_list))
        for name in cat_names:
            self.assert_(name in self.cat_names_list)

    def test_dbcnx_add_Bookmark(self):
        self.dbcnx.add_Bookmark(self.bm)
        bookmarks = self.dbcnx.get_Bookmarks()
        self.assert_(self.bm in bookmarks, "%s\n%s" %
                (self.bm, [str(bm) for bm in bookmarks if bm.url == self.bm.url]))

    def test_dbcnx_get_Bookmarks_in_specified_category(self):
        for cat_name in self.cat_names_list:
            bookmarks = self.dbcnx.get_Bookmarks(category=cat_name)
            for bm in bookmarks:
                self.assertEquals(bm.category, cat_name)

    def test_dbcnx_get_Bookmarks_with_attr_in_specified_category_and_page(self):
        for cat_name in self.cat_names_list:
            bookmarks = self.dbcnx.get_Bookmarks(page_url="/home", category=cat_name)
            for bm in bookmarks:
                self.assertEquals(bm.page_url, '/home')
                self.assertEquals(bm.category, cat_name)

    def test_dbcnx_get_Bookmarks_with_attr(self):
        self.dbcnx.add_Bookmark(self.bm)
        result = self.dbcnx.get_Bookmarks(id=self.bm.id, 
                name=self.bm.name, url=self.bm.url, 
                category=self.bm.category,
                TRACE=False)
        self.assertEquals(self.bm, result)


# --= PageData Tests =-- 
        
#class TestPageData(BookmarksTC):
#    def test_print_categories(self):
#        categories = self.dbcnx.get_categories()
#        fail = False
#        for cat in categories:
#            if cat not in self.page_data.categories:
#                fail = True
#                print cat
#            self.assert_(fail)


# --= EditLinkData Tests =--

#class TestEditLinkData(BookmarksTC):
#    def setUp(self):
#        BookmarksTC.setUp(self)
#        self.bm.add()
#        self.eld = EditLinkData(id=self.bm.id)
#
#    def tearDown(self):
#        self.bm.delete()
#        BookmarksTC.tearDown(self)
#
#    def test_load(self):
#        iter = self.bm.__dict__.iteritems()
#        while True:
#            try:
#                key, value = iter.next()
#                self.assert_(hasattr(self.eld, key))
#                self.assertEquals(getattr(self.eld, key), getattr(self.bm, key))
#            except StopIteration:
#                break
        

# --= EditPageData Tests =--

#class TestEditPageData(BookmarksTC):
#    def setUp(self):
#        BookmarksTC.setUp(self)
#        self.edit_page_data = EditPageData()
#    
#    def test_access(self):
#        for bm in self.edit_page_data:
#            self.assertEquals(bm.page_url, self.edit_page_data.page_url)


# --= Bookmark Tests =--

class TestBookmark(BookmarksTC):
    def test_Bookmark_equals_Bookmark(self):
        self.assertEquals(self.bm, Bookmark(**self.test_bm))



# --= PickleStorage tests =--
class TestCSVStorage(BookmarksTC):
    def setUp(self):
        BookmarksTC.setUp(self)
        self.cat_names_list = ['Links','Docs']
    
    def test_load_data(self):
        for bm in self.csv.bookmarks:
            self.assert_(self.csv.bookmarks.count(bm) == 1,'%s has multiple copies' % (bm) )

    def test_get_Bookmarks(self):
        bm = self.csv.get_Bookmarks(name="Something Awful")
        self.assert_(isinstance(bm, Bookmark), 'bm is of type %s' % (type(bm)) )
        self.assertEquals(bm.name, "Something Awful")
        bm_list = self.csv.get_Bookmarks(category="Docs")
        self.assert_(len(bm_list) > 0)
        for bm in bm_list:
            self.assertEquals(bm.category, 'Docs')

    def test_add_delete_Bookmark(self):
        orig_id_val = self.csv.id_val
        self.csv.add_Bookmark(self.bm)
        self.assertEqual(self.csv.id_val, orig_id_val + 1)
        self.assert_(self.bm in self.csv.bookmarks)
        self.csv.delete_Bookmark(self.bm)
        self.assert_(self.bm not in self.csv.bookmarks)
        
    def test_update_Bookmark(self):
        pass

    def test_get_PageData(self):
        pagedata = self.csv.get_PageData(self.testpage)
        self.assert_(isinstance(pagedata, PageData))
        for cat in pagedata.categories:
            self.assert_(isinstance(cat, Category))
            self.assert_(cat.bookmarks)

    def test_get_category_names(self):
        cat_names = self.csv._get_category_names(self.testpage)
        self.assertEqual(len(cat_names), len(self.cat_names_list))
        for name in cat_names:
            self.assert_(name in self.cat_names_list, 
                    (self.bm, [str(bm) for bm in self.csv.bookmarks if bm.url == self.bm.url]))

    def test_csv_get_Bookmarks_in_specified_category(self):
        for cat_name in self.cat_names_list:
            bookmarks = self.csv.get_Bookmarks(category=cat_name)
            for bm in bookmarks:
                self.assertEquals(bm.category, cat_name)

    def test_csv_get_Bookmarks_with_attr_in_specified_category_and_page(self):
        for cat_name in self.cat_names_list:
            bookmarks = self.csv.get_Bookmarks(page_url="/home", category=cat_name)
            for bm in bookmarks:
                self.assertEquals(bm.page_url, '/home')
                self.assertEquals(bm.category, cat_name)

#    def test_csv_get_Bookmarks_with_attr(self):
#        self.csv.add_Bookmark(self.bm)
#        result = self.csv.get_Bookmarks(id=self.bm.id, 
#                name=self.bm.name, url=self.bm.url, 
#                category=self.bm.category,
#                TRACE=False)
#        self.assertEquals(self.bm, result)


         

if __name__ == "__main__":
    unittest.main()


# vim:fdm=indent
