from zope.interface import Interface, Attribute, implements

def getAbsoluteSegments(path, cwd='/'):
    """
    This seems to take a maybe-relative path string and return an
    absolute path, in segments.
    It looks kind of like os.path.join(cwd, os.path.normpath(path)),
    except not OS-dependent like those are.
    """
    paths = path.split("/")

    if paths[0] == "":
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

def dirname(path, cwd='/'):
    return "/" + "/".join(getAbsoluteSegments(path, cwd)[:-1])

def fetchPath(root, paths, cwd='/'):
    currNode = root
    for path in paths:
        currNode = currNode.child(path)
    return currNode

def fetch(root, path, cwd='/'):
    paths = getAbsoluteSegments(path, cwd)
    return fetchPath(root, paths, cwd)

def getRoot(node):
    while node.parent is not node:
        node = node.parent
    return node

def basename(path, cwd='/'):
    return getAbsoluteSegments(path, cwd)[-1]



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

        - may not be the best idea ...

        returns a list of 2 element tuples:

        [ ( path, nodeObject ) ]

        eg.

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


