#!/usr/bin/env python2.3

from twisted.web.microdom import lmx
from twisted.web.woven import page
from storage import RDBStorage
from storage import CSVStorage 

import StyleSheet
import pdb
import re

TRACE = False
DEBUG = True

class Option:
    '''a convenience object for adding options to combo-boxes'''
    def __init__(self, value, text, selected=False):
        '''value is the returned value of this selection, text
is the text displayed in the combo box'''
        self.value = value
        self.text = text
        self.selected = selected

class SuperPage(page.Page):
    '''the class responsible for most of the rendering in the application.
provides the basic page setup for subclasses to override'''
    # initializs the IDataStore instance we'll be using in subclassed pages
    # this can be changed to whatever particular implementation we need for a
    # given situation (PickleStorage, etc.)
#    storage = CSVStorage.CSVStorage('storage/')
    storage = RDBStorage.RDBStorage()

    def initialize(self, *args, **kwargs):
        if 'storage' in kwargs:
            self.storage = kwargs['storage']
        page.Page.initialize(self, *args, **kwargs)

    def wvupdate_style(self,request,node,data):
        '''loads the css into the page'''
        l = lmx(node)
        h = l.head()
        h.style(type="text/css", media="all").text(StyleSheet.text)

    def wvupdate_menu(self,request,node,menu_data):
        '''provides a common menu for each page'''
        l = lmx(node)
        d = l.div()
        t = d.table(class_='menu')
        for bookmark in menu_data:
            t.tr().td().a(href=bookmark.page_url).text(bookmark.name)
        if DEBUG:
            t.tr().td().a(href="/rebuild").text("rebuild modules")
 
    def wmfactory_menudata(self, request):
        '''provides the Model for the menu's View'''
        return self.storage.get_MenuData()
   
    def wmfactory_links(self, request):
        '''provides the Model for the links View on this page'''
        # TODO: fix this!
        page_url = '/home'
        return self.storage.get_PageData(page_url)

    def wvupdate_links(self, request, node, data):
        '''renders the View for the links on this page'''
        l = lmx(node)
        t = l.table(class_='content')
        for category in data:
            t.tr().td().h1().text(category.name)
            for bookmark in category:
                t.tr().td().ul().li().a(href=bookmark.url).text(bookmark.name)


