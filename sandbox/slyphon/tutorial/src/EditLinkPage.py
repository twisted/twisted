#!/usr/bin/env python2.3

import SuperPage
from twisted.web import util
from twisted.web.microdom import lmx

import pdb

def add_opts(node, optlist):
    for opt in optlist:
        if opt.selected:
            node.option(value=opt.value, selected='selected').text(opt.text)
        else:
            node.option(value=opt.value).text(opt.text)

class EditLinkPage(SuperPage.SuperPage):
    def __init__(self, *args, **kwargs):
        self.templateFile = "templates/edit_link.html"
        SuperPage.SuperPage.__init__(self, *args, **kwargs)

    def wvupdate_combobox(self, request, node, categories):
        l = lmx(node)
        selectnode = l.select(name='category')
        selected_cat = self.bookmark.category
        optlist = []
        for cat in categories:
            if cat == selected_cat:
                optlist.append(SuperPage.Option(value=cat, selected=True, text=cat))
            else:
                optlist.append(SuperPage.Option(value=cat, text=cat))

        add_opts(selectnode, optlist)

    def wmfactory_categories(self, request):
        return self.storage.get_Category_combobox_data()

    def wvupdate_textbox(self, request, node, attr):
        l = lmx(node)
        i = l.input(type='text', name=attr, value=getattr(self.bookmark, attr))

    def wmfactory_linkname(self,request):
        return 'name'
 
    def wmfactory_url(self,request):
        return 'url'

    def getDynamicChild(self, bmark_id, request):
        self.bookmark = self.storage.get_Bookmarks(id=bmark_id)
        if 'submit' in request.args:
            args = request.args

            self.bookmark.category = args['category'][0]
            self.bookmark.url = args['url'][0]
            self.bookmark.name = args['name'][0]
            self.storage.update_Bookmark(self.bookmark)
            return util.Redirect('/edit')
        return self
