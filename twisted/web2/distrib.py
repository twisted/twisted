##### FIXME: this file probably doesn't work.

# -*- test-case-name: twisted.web.test.test_web -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Distributed web servers.

This now works as a ReverseProxy over either inet or unix sockets
"""

# System Imports
import types, os, copy, string, cStringIO
if (os.sys.platform != 'win32') and (os.name != 'java'):
    import pwd

# Twisted Imports
from twisted.python import log

# Sibling Imports
import resource
import server
import error
import static

import urlparse
from twisted.web2 import proxy
from twisted.internet import reactor, protocol

class ResourceSubscription(resource.Resource):
    isLeaf = True

    def __init__(self, host, port):
        resource.Resource.__init__(self)
        self.host = host
        self.port = port
   
    def render(self, request):
        if self.host != 'unix': 
            request.received_headers['x-forwarded-from'] = request.received_headers['host']
            request.received_headers['host'] = self.host + ':' + self.port
            request.content.seek(0,0)
        
        clientFactory = proxy.ProxyClientFactory(request.method, 
                                        request.uri, 
                                        request.clientproto,
                                        request.getAllHeaders(),
                                        request.content.read(),
                                        request)

        if self.host == 'unix':
            reactor.connectUNIX(self.port, clientFactory)
        else:
            reactor.connectTCP(self.host, self.port, clientFactory)
        
        return clientFactory.deferred

from nevow import rend
from nevow.stan import directive
from nevow.tags import *

class UserDirectoryListing(rend.Page):
    userDir = 'public_html'
    userSock = '.twisted-web.sock'
    
    def __init__(self, userdir='public_html', usersock='.twisted-web.sock'):
        rend.Page.__init__(self)
        self.userDir = userdir
        self.userSock = usersock

    stylesheet = """
    body { border: 0; padding: 0; margin: 0; background-color: #efefef; }
    h1 {padding: 0.1em; background-color: #777; color: white; border-bottom: thin white dashed;}
"""

    def getStyleSheet(self):
        return self.stylesheet

    def data_userlist(self, context, data):
        m = []
        for user in pwd.getpwall():
            pw_name, pw_passwd, pw_uid, pw_gid, pw_gecos, pw_dir, pw_shell = user
            
            realname = pw_gecos.split(',')[0]
            if not realname:
                realname = pw_name
                
            if os.path.exists(os.path.join(pw_dir, self.userDir)):
                m.append({
                        'href':'%s/' % pw_name,
                        'text':'%s (file)' % realname
                })

            if os.path.exists(os.path.join(pw_dir, self.userSock)):
                linknm = '%s.twistd' % pw_name
                m.append({
                        'href':'%s/' % linknm,
                        'text':'%s (twistd)' % realname
                })
            
        return m

    def render_userlist(self, context, data):
        return context.tag[a(href=data['href'])[ data['text'] ]]

    docFactory = rend.stan(
        html[
            head[
                title["User Directory Listing"],
                style(type="text/css")[
                    getStyleSheet
                ]
            ],
            body[
                h1["User Directory Listing"],
                ul(data=directive("userlist"), render=directive("sequence"))[
                    li(pattern="item", render=render_userlist)]]])

    def locateChild(self, request, segments):
        name = segments[0]

        if name == '':
            return self, []

        td = '.twistd'

        if name[-len(td):] == td:
            username = name[:-len(td)]
            sub=1
        else:
            username = name
            sub = 0

        try:
            pw_name, pw_passwd, pw_uid, pw_gid, pw_gecos, pw_dir, pw_shell \
                    = pwd.getpwnam(username)

        except KeyError:
            return error.NoResource(), []

        if sub:
            twistdsock = os.path.join(pw_dir, self.userSock)
            return ResourceSubscription('unix', twistdsock), segments[1:]
        
        else:
            return static.File(os.path.join(pw_dir, self.userDir)), segments[1:]
