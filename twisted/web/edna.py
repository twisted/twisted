"""An mp3 browser with playlist-generator for twisted.web"""

#TR imports
import html

from twisted.protocols import http
from twisted.web import resource, server

ROOT = 'e:' # without trailing '/'

import os
import re
import error
import static
import urllib
import socket
import random

try:
  import cStringIO
  StringIO = cStringIO
except ImportError:
  import StringIO

class Playlist(resource.Resource):
    def make_list(self, fullpath, url, recursive, shuffle, songs=None):
        # This routine takes a string for 'fullpath' and 'url', a list for
        # 'songs' and a boolean for 'recursive' and 'shuffle'. If recursive is
        # false make_list will return a list of every file ending in '.mp3' in
        # fullpath. If recursive is true make_list will return a list of every
        # file ending in '.mp3' in fullpath and in every directory beneath
        # fullpath.
        #
        # WARNING: There is no checking for the recursive directory structures
        # which are possible in most Unixes using ln -s etc...  If you have
        # such a directory structure, make_list will continue to traverse it 
        # until it hits the inherent limit in Python for the number of functions.
        # This number is quite large. I found this out the hard way :). Learn
        # from my experience...

        if songs is None:
            songs = []
        dirsorted = os.listdir(os.path.dirname(fullpath))
        dirsorted.sort()
        for name in dirsorted:
            base, ext = os.path.splitext(name)
            if extensions.has_key(ext.lower()):
                # add the song's URL to the list we're building
                songs.append(self.build_url(url, name) + '\n')

            # recurse down into subdirectories looking for more MP3s.
            if recursive and os.path.isdir(fullpath + '/' + name):
                songs = self.make_list(fullpath + '/' + name,
                                       url + '/' + urllib.quote(name),
                                       recursive, 0,	# don't shuffle subdir results
                                       songs)

        # The user asked us to mix up the results.
        if shuffle:
            count = len(songs)
            for i in xrange(count):
                j = random.randrange(count)
                songs[i], songs[j] = songs[j], songs[i]

        return songs

    def open_playlist(self, fullpath, url):
        dirpath = os.path.dirname(fullpath)
        f = open(fullpath)

        # if the first line has 'http:' or 'ftp:', then we'll assume all lines
        # are absolute and just return the open file.
        check = f.read(5)
        f.seek(0, 0)
        if check == 'http:' or check[:4] == 'ftp:':
            return f

        # they're relative file names. fix them up.
        output = [ ]
        for line in f.readlines():
            line = line.strip()
            if line[:5] == 'http:' or line[:4] == 'ftp:':
                output.append(line)
                continue
            line = os.path.normpath(line)
            if os.path.isabs(line):
                print('bad line in "%s": %s', self.path, line)
                continue
            if not os.path.exists(os.path.join(dirpath, line)):
                print('file not found (in "%s"): %s', self.path, line)
                continue
            line = line.replace("\\", "/")  # if we're on Windows
            output.append(self.build_url(url, line))

        f = StringIO.StringIO(output.join('\n') + '\n')
        return f

    def build_url(self, url, file=''):
        host = self.request.getHost()
        return 'http://%s:%d%s' % (host[1], host[2], urllib.quote(url+'/'+file))

    def __init__(self, urlpath, fullpath):
        resource.Resource.__init__(self)
        self.path = urlpath
        self.fullpath = fullpath
        self.url = os.path.dirname(urlpath)
        
    def render(self, request):
        self.request = request
        type = 'audio/x-mpegurl'
        base, ext = os.path.splitext(self.path)
        name = os.path.basename(self.path)
        url = self.url
        if name == 'all.m3u' or name == 'allrecursive.m3u' or \
           name == 'shuffle.m3u' or name == 'shufflerecursive.m3u':
            recursive = name == 'allrecursive.m3u' or name == 'shufflerecursive.m3u'
            shuffle = name == 'shuffle.m3u' or name == 'shufflerecursive.m3u'

            # generate the list of URLs to the songs
            songs = self.make_list(self.fullpath, url, recursive, shuffle)

            f = StringIO.StringIO(''.join(songs))
            size = len(f.getvalue())
        else:
          base, ext = os.path.splitext(base)
          if extensions.has_key(ext.lower()):
              f = StringIO.StringIO(self.build_url(url, os.path.basename(base)) + ext + '\n')
              size = len(f.getvalue())
          # a bit modified from the original edna here.
          # this should be modified for resident playlists: .m3u.m3u ;)
          if ext.lower == '.m3u':
              f = self.open_playlist(self.fullpath, url)
              size = len(f.getvalue())
          
        request.setHeader('content-type', type)
        static.FileTransfer(f, size, request)
        return server.NOT_DONE_YET
      
class WebEdna(html.Interface):
    def buildPath(self, path):
        fullpath = os.path.join(self.path, path)
        #fullpath = self.root + self.path + path
        fullpath = os.path.normpath(fullpath)
        fullpath = self.root + fullpath
        fullpath = fullpath.replace('\\', '/')
	while fullpath.count('//') > 0:
            fullpath = fullpath.replace('//', '/')
        return fullpath
        

    def __init__(self, root=ROOT, path=''):
        if path == '':
            path = '/'
        if path[0] is not '/':
            path = '/' + path
        if path[-1:] is not '/':
            path = path + '/'
        self.path = path
        self.root = root
        self.children = {}

    def getChild(self, path, request):
        if path == '..':
            return error.NoResource()
        newpath = os.path.join(self.path, path)
        newpath = newpath.replace('\\', '/')
        # A directory
        if path == '':
            if os.path.isdir(self.buildPath(path)):
                return WebEdna(self.root, self.path)
        base, ext = os.path.splitext(path)
        if ext == '.m3u':
            return Playlist(request.path, self.buildPath(path))
        if os.path.isfile(self.buildPath(path)):
            return static.File(self.buildPath(path))
        return WebEdna(self.root, newpath)

    def renderDirlist(self, dirlist, request):
#        content = '<table border="0"><tr><td>Directory listing</td><td>...</td></tr>'
        content = '<table border="0">'
        for filename in dirlist:
            content = content + '<tr><td><a href="%s%s">%s</a></td><td>(Directory)</td>' \
                                % (request.path, filename, filename)
            if not (filename == '..'):
                content = content + '<td><a href="%s%sallrecursive.m3u">play</a>&nbsp;'\
                          % (request.path, filename) \
                          + '<a href="%s%sshufflerecursive.m3u">shuffle</a></td>' \
                          % (request.path, filename)
            content = content + '</tr>'
        content = content + "</table>"
        return content

    def renderFilelist(self, filelist, request):
#        content = '<table border="0"><tr><td>Directory listing</td><td>...</td></tr>'
        content = '<table border="0">'
        for file in filelist:
            content = content + '<tr><td><a href="%s%s.m3u">%s</a></td><td>(File)</td></tr>' \
                      % (request.path, file, file)
        content = content + ('<tr><td>[<a href="%sall.m3u">play all</a>]&nbsp;' \
                  % (request.path) \
                  + '[<a href="%sshuffle.m3u">shuffle</a></td>]</tr>') \
                  % (request.path)
        content = content + "</table>"
        return content

    def renderListing(self, request):
        ifilelist = os.listdir(self.buildPath(''))
        dirlist = []
        filelist = []
        if request.path[-1:] is not '/':
            request.path = request.path + '/'
        if self.path is not '/':
            dirlist.append('..')
        for file in ifilelist:
            if os.path.isdir(self.buildPath(file)):
                dirlist.append(file + '/')
            else:
                filelist.append(file)
        content = ''
        if len(dirlist) > 0:
            content = content + self.box(request, 'Directories', self.renderDirlist(dirlist, request))
        if len(filelist) > 0:
            content = content + self.box(request, 'Files', self.renderFilelist(filelist, request))
        
        return content

    def render(self, request):
        content = 'path:' + request.path
        content = content + self.renderListing(request)
        content = content + 'hello?'
        return self.webpage(request, "MP3 Directory: " + self.path, content)
    
        
# Stuff lended from edna

# a pattern used to trim leading digits, spaces, and dashes from a song
### would be nice to get a bit fancier with the possible trimming
re_trim = re.compile('[-0-9 ]*-[ ]*(.*)')

# Extensions that WinAMP can handle: (and their MIME type if applicable)
extensions = { 
    '.mp3' : 'audio/mpeg',
    '.mid' : 'audio/mid',
    '.mp2' : 'video/mpeg',        ### is this audio or video? my Windows box
                                  ### says video/mpeg
#    '.cda',                      ### what to do with .cda?
    '.it'  : 'audio/mid',
    '.xm'  : 'audio/mid',
    '.s3m' : 'audio/mid',
    '.stm' : 'audio/mid',
    '.mod' : 'audio/mid',
    '.dsm' : 'audio/mid',
    '.far' : 'audio/mid',
    '.ult' : 'audio/mid',
    '.mtm' : 'audio/mid',
    '.669' : 'audio/mid',
    '.asx' : 'video/x-ms-asf',
    '.mpg' : 'video/mpeg',
    }

# Extensions of images: (and their MIME type)
picture_extensions = { 
    '.gif' : 'image/gif',
    '.jpeg' : 'image/jpeg',
    '.jpg' : 'image/jpeg',
    '.png' : 'image/png',
    }

any_extensions = {} 
any_extensions.update(extensions)
any_extensions.update(picture_extensions)
