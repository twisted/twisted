#!/usr/bin/env python2.3

from twisted.web.microdom import lmx
from twisted.web.woven.widgets import KeyedList
from twisted.web.woven.model import StringModel
from SuperPage import SuperPage
from SuperPage import Option

from EditPageData import EditPageData

import Constant

import pdb

def DSU(List, Decorate, Undecorate):
    '''a function for sorting our list of bookmarks,
this implements the Decorate-Sort-Undecorate pattern, all credit goes to
exarkun for this implementation. for more information see 
http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/52234
'''
    L2 = map(Decorate, List)
    L2.sort()
    return map(Undecorate, L2)

class EditPage(SuperPage):
    '''Our page that allows the user to select a bookmark to edit or delete'''
    def __init__(self, *args, **kwargs):
        self.templateFile = "templates/edit_page.html"
        SuperPage.__init__(self, *args, **kwargs)

    def wvupdate_table_data(self, request, node, data):
        '''renders the table to allow users to edit bookmarks'''
        # lmx is a handy function for building dom 
        # structures (such as xml, html, xhtml, etc.)
        # look at twisted.web.microdom and the PicturePile 
        # tutorial for more information
        l = lmx(node)
        t = l.table(class_='content').form(method='post', action='')
        data = DSU(data, lambda e: (e.category, e), lambda e: e[1])
        for d in data:
            tr = t.tr()
            tr.td().a(href="/%s/%s/" % ('EditLink', d.id)).text('edit')
            tr.td().a(href="/%s/%s/" % ('DeleteLink', d.id)).text('delete')
            tr.td().text(d.category)
            tr.td().text(d.id)
            tr.td().a(href=d.url).text(d.name)
            tr.td().text(d.url)
        td = t.tr().td(colspan='4', align='right')

    def wmfactory_db_table(self, request):
        '''retrieves the appropriate model for this table'''
        return self.storage.get_EditPageData()

    def getDynamicChild(self, name, request):
        '''no magic here, so if someone requests a child we don't have, just
return a new instance of EditPage, which ensures that the most recent copy
of the data from the DataStore is presented
'''
        return EditPage()

