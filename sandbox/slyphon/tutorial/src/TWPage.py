#!/usr/bin/env python2.3

from twisted.web.woven import page
from SuperPage import SuperPage
from PageData import PageData
import dbcnx

TRACE=False

class TWPage(SuperPage):
    templateFile="templates/tw_twisted.html"
    def initialize(self, *args, **kwargs):
        if TRACE:
			print 'TWPage.initialize'
        SuperPage.initialize(self, *args, **kwargs)

    def wmfactory_links(self,request):
        if TRACE:
			print 'TWPage.wmfactory_links'
        page_url = '/twpage'
        return PageData(page_url)
        
    def getDynamicChild(self, name, request):
        if TRACE:
			print 'TWPage.getDynamicChild'
        return TWPage()

