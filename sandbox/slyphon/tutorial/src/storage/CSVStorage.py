#!/usr/bin/env python2.3

import sys
import os.path
sys.path.append("./../")
import Bookmark
import Category
import PageData
import BookmarkContainer
from cStringIO import StringIO
import pdb
import csv

class CSVStorage:
    bookmark_file = 'bookmarks.csv'
    menu_file = 'menu.csv'
    id_val = 0
    def __init__(self, prepath='./'):
        self.bookmark_file = os.path.join(prepath, self.bookmark_file)
        self.menu_file = os.path.join(prepath, self.menu_file)
        self._load_data(prepath)

    def _load_data(self, prepath='./'):
        # load bookmarks
        self.bookmarks, self.menu = [], []
        csv_reader = csv.reader(file(self.bookmark_file, 'r'))
        keywords = ['category','url','id','name','page_url']
        for row in csv_reader:
            # csv file is in the format category,url,id,name,page_url
            kwargs = dict(zip(keywords, row))
            self.bookmarks.append(Bookmark.Bookmark(**kwargs))

        csv_reader = csv.reader(file(self.menu_file, 'r'))      
        keywords = ['id','name','page_url']
        for row in csv_reader:
            # csv file is in the format category,url,id,name,page_url
            kwargs = dict(zip(keywords, row))
            self.menu.append(Bookmark.Bookmark(**kwargs))

        # find highest id number and save it so we can generate unique id's
        for bm in self.bookmarks:
            if bm.id > self.id_val:
                self.id_val = int(bm.id)
        

    def _flush_data(self):
        # write the bookmark data
        fd = file(self.bookmark_file, 'w')
        writer = csv.writer(fd)
        for bm in self.bookmarks:
            writer.writerow(bm.csv_row)
        del(writer)
        fd.close()

        fd = file(self.menu_file, 'w')
        writer = csv.writer(fd)
        for bm in self.menu:
            writer.writerow(bm.csv_row)
        del(writer)
        fd.close()


    def get_PageData(self, page_url='/home'):
        return PageData.PageData(categories=self._get_Category_list_for_page(page_url), page_url=page_url)
    
    def _get_Category_list_for_page(self, page_url='/home'):
        '''returns a list of Category objects for the specified page_url'''
        cat_name_list = self._get_category_names(page_url=page_url)
        cat_list = []
        for cat_name in cat_name_list:
            bookmark_list = self.get_Bookmarks(category=cat_name)
            cat_list.append(Category.Category(bookmarks=bookmark_list, 
                            page_url=page_url, name=cat_name))
        return cat_list


    def _get_category_names(self, page_url='/home'):
        # gets all category names for a given page and removes duplicates
        result = []
        for bm in self.bookmarks:
            if bm.page_url == page_url and bm.category not in result:
                result.append(bm.category)
        return result

    def get_Category_combobox_data(self, page_url='/home'):
        return self._get_category_names(page_url)

    def get_MenuData(self):
        return BookmarkContainer.BookmarkContainer(bookmarks=self.menu)

    def get_EditPageData(self):
        return BookmarkContainer.BookmarkContainer(self.bookmarks)

    def delete_Bookmark(self, bookmark):
        try:
            self.bookmarks.remove(bookmark)
        except Exception, e:
            pdb.set_trace() 
        self._flush_data()
        self._load_data()

    def update_Bookmark(self, bookmark):
        # this is a pretty awful function. it searches every bookmark
        # but it is simple and effective for this example
        # it would probably be more efficient to implement a dictionary/index of 
        # id values
        for index, bm in enumerate(self.bookmarks):
            if bm.id == bookmark.id:
                self.bookmarks[index] = bookmark
        self._flush_data()
        self._load_data()

    def add_Bookmark(self, bookmark):
        self.id_val += 1
        bookmark.id = str(self.id_val)
        self.bookmarks.append(bookmark)
        self._flush_data()
        self._load_data()

    def get_Bookmarks(self,  **kwargs):
        result = []
        for bm in self.bookmarks: 
            if bm.matches_values(**kwargs):
                result.append(bm)

        if len(result) == 1:
            return result[0]
        return result
 

if __name__ == "__main__":
    c = CSVStorage()



