#!/usr/bin/env python2.3

from Category import Category

class PageData:
    '''holds all Category classes for a given page'''
    def __init__(self, categories, page_url):
        self.categories = categories
        self.page_url = page_url

    def __getitem__(self, key):
        return self.categories[key]

    def __setitem__(self, key, value):
        self.categories[key] = value

    def __iter__(self):
        return iter(self.categories)

    def _reindex(self):
        '''unimplemented: can be implemented in subclasses
used to create an index of bookmark values'''
        raise NotImplementedError

