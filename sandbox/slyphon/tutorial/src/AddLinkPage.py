#!/usr/bin/env python2.3

from twisted.web.microdom import lmx
from twisted.web import util
from twisted.web.woven import widgets

import SuperPage
import Bookmark

def add_opts(node, optlist):
    for opt in optlist:
        node.option(value=opt.value).text(opt.text)

class AddLinkPage(SuperPage.SuperPage):
    def __init__(self, *args, **kwargs):
        self.templateFile = "templates/add_link.html"
        self.addSlash = False
        SuperPage.SuperPage.__init__(self, *args, **kwargs)

    def wmfactory_categories(self, request):
        data = self.storage.get_Category_combobox_data()
        return data

    def wvupdate_combobox(self, request, node, data):
        l = lmx(node)
        s = l.select(name='category', selected='2')
        optlist = [SuperPage.Option(category, category) for category in data]
        add_opts(s, optlist)

    def wvupdate_textbox(self, request, node, attr):
        l = lmx(node)
        i = l.input(type='text', name=attr, value="")

    def wmfactory_linkname(self,request):
        return 'name'
 
    def wmfactory_url(self,request):
        return 'url'


    def getDynamicChild(self, name, request):
        if 'submit' in request.args:
            print 'found submit in request.args'
            args = request.args
            category = args['category'][0]
            url = args['url'][0]
            name = args['name'][0]
            b = Bookmark.Bookmark(page_url='/home', category=category, url=url, name=name)
            self.storage.add_Bookmark(b)
            return util.Redirect('/edit')
#        return self
    

