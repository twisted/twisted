# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""Directory listing."""

# system imports
import os
import urllib
import stat
import time

# twisted imports
from twisted.web2 import iweb, resource, http, http_headers

def formatFileSize(size):
    if size < 1024:
        return '%i' % size
    elif size < (1024**2):
        return '%iK' % (size / 1024)
    elif size < (1024**3):
        return '%iM' % (size / (1024**2))
    else:
        return '%iG' % (size / (1024**3))

class DirectoryLister(resource.Resource):
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
        resource.Resource.__init__(self)

    def data_listing(self, request, data):
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
                    'size': '',
                    'type': '-',
                    'lastmod': time.strftime("%Y-%b-%d %H:%M", time.localtime(st.st_mtime))
                    })
            else:
                from twisted.web2.static import getTypeAndEncoding
                mimetype, encoding = getTypeAndEncoding(
                    path,
                    self.contentTypes, self.contentEncodings, self.defaultType)
                
                filesize = st.st_size
                files.append({
                    'link': url,
                    'linktext': path,
                    'size': formatFileSize(filesize),
                    'type': mimetype,
                    'lastmod': time.strftime("%Y-%b-%d %H:%M", time.localtime(st.st_mtime))
                    })

        return files

    def __repr__(self):  
        return '<DirectoryLister of %r>' % self.path
        
    __str__ = __repr__


    def render(self, request):
        title = "Directory listing for %s" % urllib.unquote(request.path)
    
        s= """<html><head><title>%s</title><style>
          th, .even td, .odd td { padding-right: 0.5em; font-family: monospace}
          .even-dir { background-color: #efe0ef }
          .even { background-color: #eee }
          .odd-dir {background-color: #f0d0ef }
          .odd { background-color: #dedede }
          .icon { text-align: center }
          .listing {
              margin-left: auto;
              margin-right: auto;
              width: 50%%;
              padding: 0.1em;
              }

          body { border: 0; padding: 0; margin: 0; background-color: #efefef;}
          h1 {padding: 0.1em; background-color: #777; color: white; border-bottom: thin white dashed;}
</style></head><body><div class="directory-listing"><h1>%s</h1>""" % (title,title)
        s+="<table>"
        s+="<tr><th>Filename</th><th>Size</th><th>Last Modified</th><th>File Type</th></tr>"
        even = False
        for row in self.data_listing(request, None):
            s+='<tr class="%s">' % (even and 'even' or 'odd',)
            s+='<td><a href="%(link)s">%(linktext)s</a></td><td align="right">%(size)s</td><td>%(lastmod)s</td><td>%(type)s</td></tr>' % row
            even = not even
                
        s+="</table></div></body></html>"
        response = http.Response(200, {}, s)
        response.headers.setHeader("content-type", http_headers.MimeType('text', 'html'))
        return response

__all__ = ['DirectoryLister']
