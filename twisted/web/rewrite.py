# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
#
from twisted.web import resource

class RewriterResource(resource.Resource):

    def __init__(self, orig, *rewriteRules):
	resource.Resource.__init__(self)
        self.resource = orig
        self.rewriteRules = list(rewriteRules)

    def _rewrite(self, request):
        for rewriteRule in self.rewriteRules:
            rewriteRule(request)

    def getChild(self, path, request):
        request.postpath.insert(0, path)
        request.prepath.pop()
        self._rewrite(request)
        path = request.postpath.pop(0)
        request.prepath.append(path)
        return self.resource.getChildWithDefault(path, request)

    def render(self, request):
        self._rewrite(request)
        return self.resource.render(request)


def tildeToUsers(request):
    if request.postpath and request.postpath[0][:1]=='~':
        request.postpath[:1] = ['users', request.postpath[0][1:]]
        request.path = '/'+'/'.join(request.prepath+request.postpath)

def alias(aliasPath, sourcePath):
    """
    I am not a very good aliaser. But I'm the best I can be. If I'm
    aliasing to a Resource that generates links, and it uses any parts
    of request.prepath to do so, the links will not be relative to the
    aliased path, but rather to the aliased-to path. That I can't
    alias static.File directory listings that nicely. However, I can
    still be useful, as many resources will play nice.
    """
    sourcePath = sourcePath.split('/')
    aliasPath = aliasPath.split('/')
    def rewriter(request):
        if request.postpath[:len(aliasPath)] == aliasPath:
            after = request.postpath[len(aliasPath):]
            request.postpath = sourcePath + after
            request.path = '/'+'/'.join(request.prepath+request.postpath)
    return rewriter
