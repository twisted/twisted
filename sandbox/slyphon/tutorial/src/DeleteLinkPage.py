#!/usr/bin/env python2.3

import SuperPage
from twisted.web import util

import pdb

class DeleteLinkPage(SuperPage.SuperPage):
    def __init__(self, id=None, *args, **kwargs):
        self.template = "<html></html>"
        SuperPage.SuperPage.__init__(self, *args, **kwargs)

    def getDynamicChild(self, bmark_id, request):
        bookmark = self.storage.get_Bookmarks(id=bmark_id)
        self.storage.delete_Bookmark(bookmark)
        return util.Redirect('/edit')

