
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

"""I hold the lowest-level Resource class."""


# System Imports
import string

class Resource:
    """I define a web-accessible resource.
    
    I serve 2 main purposes; one is to provide a standard representation for
    what HTTP specification calls an 'entity', and the other is to provide an
    abstract directory structure for URL retrieval.
    """

    server = None

    def __init__(self):
        """Initialize.
        """
        self.children = {}

    isLeaf = 0

    classChildren = {}

    def getChild(self, path, request):
        """Retrieve a 'child' resource from me.

        Arguments:
        
           path: a string, describing the child

           request: a twisted.web.server.Request specifying meta-information
           about the request that is being made for this child.

        Implement this to create dynamic resource generation -- resources which
        are always available may be registered with self.putChild().

        This will not be called if the class-level variable 'isLeaf' is set in
        your subclass; instead, the 'postpath' attribute of the request will be
        left as a list of the remaining path elements.

        For example, the URL /foo/bar/baz will normally be::
        
          |  site.resource.getChild('foo').getChild('bar').getChild('baz').

        However, if the resource returned by 'bar' has isLeaf set to true, then
        the getChild call will never be made on it.
        """
        return error.NoResource()

    def getChildWithDefault(self,path, request):
        """(internal) Retrieve a static or dynamically generated child resource from me.

        Arguments are similiar to getChild.

        This will check to see if I have a pre-registered child resource of the
        given name, and call getChild if I do not.
        """
        for dict in (self.children, self.classChildren):
            if dict.has_key(path):
                return dict[path]

        return self.getChild(path, request)


    def putChild(self, path, child):
        """Register a child with me.
        """
        self.children[path] = child
        child.server = self.server


    def render(self, request):
        """Render a given resource.

        This must be implemented in all subclasses of Resource.

        The return value of this method will be the rendered page, unless the
        return value is twisted.web.server.NOT_DONE_YET, in which case it is
        this class's responsability to write the results to
        request.write(data), then call request.finish().
        """
        raise "%s called" % str(self.__class__.__name__)

#t.w imports
#This is ugly, I know, but since error.py directly access resource.Resource
#during import-time (it subclasses it), the Resource class must be defined
#by the time error is imported.
import error
