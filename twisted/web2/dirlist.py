# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""Directory listing."""

# system imports
import os
import urllib
import stat

# twisted imports
from twisted.web2 import iweb

from nevow import rend, loaders
from nevow.tags import *

def formatFileSize(size):
    if size < 1024:
        return '%ib' % size
    elif size < (1024**2):
        return '%iK' % (size / 1024)
    elif size < (1024**3):
        return '%iM' % (size / (1024**2))
    else:
        return '%iG' % (size / (1024**3))

class DirectoryLister(rend.Page):
    def __init__(self, pathname, dirs=None,
                 contentTypes={},
                 contentEncodings={},
                 defaultType='text/html'):
        self.contentTypes = contentTypes
        self.contentEncodings = contentEncodings
        self.defaultType = defaultType
        # dirs allows usage of the File to specify what gets listed
        self.dirs = dirs
        self.path = pathname
        rend.Page.__init__(self)

    def data_listing(self, context, data):
        from twisted.web2.static import getTypeAndEncoding

        if self.dirs is None:
            directory = os.listdir(self.path)
            directory.sort()
        else:
            directory = self.dirs

        files = []

        for path in directory:
            url = urllib.quote(path, '/')
            fullpath = os.path.join(self.path, path)
            try:
                st = os.stat(fullpath)
            except OSError:
                continue
            if stat.S_ISDIR(st.st_mode):
                url = url + '/'
                files.append({
                    'link': url,
                    'linktext': path + "/",
                    'type': '[Directory]',
                    'filesize': '',
                    'encoding': '',
                    })
            else:
                mimetype, encoding = getTypeAndEncoding(
                    path,
                    self.contentTypes, self.contentEncodings, self.defaultType)
                filesize = st.st_size
                files.append({
                    'link': url,
                    'linktext': path,
                    'type': '[%s]' % mimetype,
                    'filesize': formatFileSize(filesize),
                    'encoding': (encoding and '[%s]' % encoding or '')})

        return files

    def data_header(self, context, data):
        request = context.locate(iweb.IRequest)
        return "Directory listing for %s" % urllib.unquote(request.uri)

    def render_tableLink(self, context, data):
        return a(href=data['link'])[data['linktext']]

    def __repr__(self):  
        return '<DirectoryLister of %r>' % self.path
        
    __str__ = __repr__


    docFactory = loaders.stan(html[
      head[
        title(data=directive('header'))[str],
        style['''
          th, .even td, .odd td { padding-right: 0.5em; }
          .even-dir { background-color: #efe0ef }
          .even { background-color: #eee }
          .odd-dir {background-color: #f0d0ef }
          .odd { background-color: #dedede }
          .icon { text-align: center }
          .listing {
              margin-left: auto;
              margin-right: auto;
              width: 50%;
              padding: 0.1em;
              }

          body { border: 0; padding: 0; margin: 0; background-color: #efefef;}
          h1 {padding: 0.1em; background-color: #777; color: white; border-bottom: thin white dashed;}
          ''']
      ],
      body[div(_class='directory-listing')[
        h1(data=directive('header'))[str],
        table(render=rend.sequence, data=directive('listing'))[
           tr(pattern="header")[
             th["Filename"],
             th["Size"],
             th["Content type"],
             th["Content encoding"],
           ],
           tr(_class="even", pattern="item")[
             td[a(render=directive("tableLink"))],
             td(data=directive("filesize"))[str],
             td(data=directive("type"))[str],
             td(data=directive("encoding"))[str],
           ],
           tr(_class="odd", pattern="item")[
             td[a(render=directive("tableLink"))],
             td(data=directive("filesize"))[str],
             td(data=directive("type"))[str],
             td(data=directive("encoding"))[str],
           ]
        ]
      ]]
    ])
