# Twisted, the Framework of Your Internet Copyright (C) 2003 Matthew
# W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Directory listing."""

# system imports
from os.path import join as joinpath
import urllib, os

# sibling imports
import page, model, widgets, view

# twisted imports
from twisted.web.microdom import lmx
from twisted.web.domhelpers import RawText
from twisted.python.filepath import FilePath
from twisted.web.static import File, getTypeAndEncoding


class DirectoryLister(page.Page):
    template = '''
    <html>
    <head>
    <title model="header"> </title>
    <style>
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

    body { border: 0; padding: 0; margin: 0; background-color: #efefef; }
    h1 {padding: 0.1em; background-color: #777; color: white; border-bottom: thin white dashed;}

    </style>
    </head>
    
    <body>
    <h1 model="header"> </h1>

    <table view="List" model="listing">
        <tr pattern="listHeader">
            <th>Filename</th>
            <th>Content type</th>
            <th>Content encoding</th>
        </tr>
        <tr class="even" pattern="listItem">
            <td><a model="link" view="Link" /></td>
            <td model="type" view="Text"></td>
            <td model="encoding" view="Text"></td>
        </tr>
        <tr class="odd" pattern="listItem">
            <td><a model="link" view="Link" /></td>
            <td model="type" view="Text"></td>
            <td model="encoding" view="Text"></td>
        </tr>
    </table>
    
    </body>
    </html>
    '''

    def __init__(self, pathname, dirs=None,
                 contentTypes=File.contentTypes,
                 contentEncodings=File.contentEncodings,
                 defaultType='text/html'):
        self.contentTypes = contentTypes
        self.contentEncodings = contentEncodings
        self.defaultType = defaultType
        # dirs allows usage of the File to specify what gets listed
        self.dirs = dirs
        self.path = pathname
        page.Page.__init__(self)

    def wmfactory_listing(self, request):
        if self.dirs is None:
            directory = os.listdir(self.path)
            directory.sort()
        else:
            directory = self.dirs

        files = []; dirs = []

        for path in directory:
            url = urllib.quote(path, "/")
            if os.path.isdir(os.path.join(self.path, path)):
                url = url + '/'
                dirs.append({'link':{"text": path + "/", "href":url},
                             'type': '[Directory]', 'encoding': ''})
            else:
                mimetype, encoding = getTypeAndEncoding(path, self.contentTypes,
                                                        self.contentEncodings,
                                                        self.defaultType)
                files.append({
                    'link': {"text": path, "href": url},
                    'type': '[%s]' % mimetype,
                    'encoding': (encoding and '[%s]' % encoding or '')})

        return files + dirs

    def wmfactory_header(self, request):
        return "Directory listing for %s" % urllib.unquote(request.uri)

    def __repr__(self):  
        return '<DirectoryLister of %r>' % self.path
        
    __str__ = __repr__
