#!/usr/bin/env python2.3

from twisted.python import components

class IDataStore(components.Interface):
    '''a common interface for data objects to connect with'''
    def get_categories(self, page_url):
        '''returns the Categories for a given page_url'''
        pass

    def get_PageData(self, page_url):
        '''gets the PageData object for a given page_url'''
        pass

    def get_MenuData(self):
        '''returns a menu data object'''
        pass

    def delete_Bookmark(self, bookmark):
        '''deletes a bookmark data object from the data store'''
        pass

    def update_Bookmark(self, bookmark):
        '''updates a given bookmark object's attributes in the data store'''
        pass

    def add_Bookmark(self, bookmark):
        '''adds a new bookmark to the data store'''
        pass

    def get_Bookmarks(self, **kwargs):
        '''returns list of Bookmarks with attribute(s) specified as kwargs. 
**kwargs must contain one of [id, url, name, page_url, category] '''
        pass

