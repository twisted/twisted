#!/usr/bin/env python2.3

import pdb

class Bookmark(object):
    def __init__(self, id=None, page_url=None, category=None, 
                 name=None, url=None):

        # the primary id of this bookmark (a unique int identifier)
        self.id = id         

        # the url of the local page this link belongs to
        self.page_url = page_url   

        # the heading under which this link should appear 
        self.category = category   

        # the displayed name of this link (appears between the <a> and </a>)
        self.name = name       

        # the url this link points to (the <a href=> points here)
        self.url = url        

    def _get_csv_row(self):
        attrib_list = [self.category, self.url, self.id, self.name, self.page_url]
        return [a for a in attrib_list if a]
    csv_row = property(_get_csv_row, doc='''returns a list representation 
of this object properly formatted for writing to our CSVStorage module''')

    def matches_values(self, **kwargs):
        '''tests to see if this bookmark matches the attribute values
given as kwargs. returns a boolean value'''
        for key, val in kwargs.iteritems():
            if not getattr(self, key) == val:
                return False
        return True

    def __cmp__(self, other):
        if (self.id == other.id and
            self.page_url == other.page_url and
            self.category == other.category and
            self.name == other.name and
            self.url == other.url):
            return 0
        else:
            return 1

    def __str__(self):
        astr = ""
        iter = self.__dict__.iteritems()
        while True:
            try:
                astr = ''.join([astr, '%s: %s\n' % iter.next()])
            except StopIteration:
                break
        return astr
    
        

