#!/usr/bin/env python2.3

from twisted.web.woven  import page
from twisted.web        import util, error

import pdb
import os.path

from TWPage import TWPage
from EditPage import EditPage
from SuperPage  import SuperPage
from AddLinkPage import AddLinkPage
from EditLinkPage import EditLinkPage
from DeleteLinkPage import DeleteLinkPage
from EditLinkSubmit import EditLinkSubmit


# I use the global TRACE to turn on and off debugging message output
TRACE = False

class HomePage(SuperPage):
    '''this is the main controlling page for this application. It's the
glue between all the separate resources and pages we use, and it handles
the storage object. It subclasses SuperPage, which provides the view
for the root page, and basic utility functions for the other pages.
'''
    # the html template that we'll use for this page
    templateFile="templates/tw_docs.html"

    def initialize(self, *args, **kwargs):
        '''instead of __init__ we initialize'''
        if TRACE:
			print 'HomePage.initialize'
#        if 'storage' not in kwargs:
#            raise SystemExit("no storage object!")
        SuperPage.initialize(self, *args, **kwargs)

    # TODO: have HomePage accept storage object, then do
    #       SuperPage.storage = storage

    # TODO: Figure out what wmfactory_subpages does!!
    def wmfactory_subpages(self, request):
        if TRACE:
            print 'HomePage.wmfactory_subpages'
        keys = self.children.keys()
        keys.sort()
        return keys

    def wchild_edit(self, request):
        '''The page where the user selects links to edit, 
delete or where the user can add a link'''
        return EditPage()
    
    def wchild_rebuild(self, request):
        '''for rebuilding all modules in the program
without having to kill the twistd server'''
        from SiteRebuild import RebuildPage
        return RebuildPage(request=request)
    
    def wchild_home(self, request):
        '''this is for when people request /home'''
        return HomePage()

    def wchild_AddLink(self, request):
        '''this is the /AddLink resource'''
#        return AddLinkPage(storage=self.storage)
        return AddLinkPage()

    def getDynamicChild(self, name, request):
        '''When a page recieves a request for a child page, and no wchild_* is found
control is given to this method.

this is also where we parse and handle the requests to 
either edit or delete a file
'''
        #
        # the EditLink or DeleteLink url is recieved in the form '/EditLink/NN'
        # where NN is the id-number of the desired bookmark
        #
        path = request.uri.split('/')
        while True:
            try:
                path.remove('')
            except ValueError, e:
                break
        #
        # here we check the first part of the path requested 
        #
        # the bookmark id will wind up as the 'name' arg in 
        # EditLinkPage and DeleteLinkPage's .getDynamicChild(). 
        #
        if path[0] == 'EditLink':
            return EditLinkPage()   
        if path[0] == 'DeleteLink':
            return DeleteLinkPage()

        # if we get to here, we return an error, because the 
        # requested page was not found
        return error.NoResource('resource was not found')



