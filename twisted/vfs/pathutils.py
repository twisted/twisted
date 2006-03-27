from zope.interface import Interface, Attribute, implements

def getAbsoluteSegments(path, cwd='/'):
    """
    @param path: either a string or a list of string segments
    which specifys the desired path.  may be relative to the cwd

    @param cwd: optional string specifying the current working directory

    returns a list of string segments which most succinctly
    describe how to get to path from root
    """
    if not isinstance(path, list): paths = path.split("/")
    else: paths = path

    if len(paths) and paths[0] == "":
        paths = paths[1:]
    else:
        paths = cwd.split("/") + paths

    result = []

    for path in paths:
        if path == "..":
            if len(result) > 1:
                result = result[:-1]
            else:
                result = []

        elif path not in ("", "."):
            result.append(path)

    return result

def fetch(root, path, cwd='/'):
    """
    @param root: IFileSystemContainer which represents the root node
    of the filesystem

    @param path: either a string or a list of string segments
    which specifys the desired path.  may be relative to the cwd

    @param cwd: optional string specifying the current working directory

    returns node described by path relative to the cwd
    """
    paths = getAbsoluteSegments(path, cwd)
    currNode = root
    for path in paths:
        currNode = currNode.child(path)
    return currNode

def basename(path, cwd='/'):
    s = getAbsoluteSegments(path, cwd)
    if s:
        return s[-1]
    return ''

def dirname(path, cwd='/'):
    return "/" + "/".join(getAbsoluteSegments(path, cwd)[:-1])

def getRoot(node):
    while node.parent is not node:
        node = node.parent
    return node

def getSegments(node):
    ret = []
    while node.parent is not node:
        ret.append(node.name)
        node = node.parent
    ret.reverse()
    return ret





class IFileSystem(Interface):

    root = Attribute("root IFileSystemNode of the IFileSystem")
    pathToCWD = Attribute("path to current working directory")

    def absPath(path):
        """
        returns a normalized absolutized version of the pathname path
        """

    def splitPath(path):
        """
        returns a normalized absolutized version of the pathname path
        split on the filesystem's directory seperator
        """

    def joinPath(tail, head):
        """
        joins the two paths, tail and head
        """

    def dirname(path):
        """
        returns the directory name of the container for path
        """

    def basename(path):
        """
        returns the base name of pathname path
        """

    def fetch(path):
        """
        returns a node object representing the file with pathname path
        """

    def _getImplicitChildren(dir):
        """
        returns implicit children for a given dir
        this is placed in the filesystem so that the same
        directory can have different implicit children depending
        on what sort of filesystem it has been placed in

        (This may not be the best idea)

        returns a list of 2 element tuples, C{[ ( path, nodeObject ) ]}, e.g.::

            [ ( ".", dir ), ( "..", dir.parent ) ]
        """


class FileSystem:
    """
    Wraps unix-like VFS backends, in which directory separator is '/',
    root's path is '/', and all directories have '.' and '..'.

    Effectively, this is just a convenience wrapper around the other
    functions in this module which remembers the root node and the
    current working directory.
    """

    implements(IFileSystem)

    def __init__(self, root, pathToCWD="/"):
        self.root             =  root
        self.root.filesystem  =  self
        self.pathToCWD        = pathToCWD

    def absPath(self, path):
        return "/" + "/".join(self.splitPath(path))

    def splitPath(self, path):
        return getAbsoluteSegments(path, self.pathToCWD)

    def joinPath(self, tail, head):
        if tail == "/":
            return tail + head
        else:
            return tail + "/" + head

    def dirname(self, path):
        return dirname(path, self.pathToCWD)

    def basename(self, path):
        return basename(path, self.pathToCWD)

    def fetch(self, pathToFile="."):
        return fetch(self.root, pathToFile, self.pathToCWD)

    def _getImplicitChildren(self, dir):
        return [(".", dir), ("..", dir.parent)]


