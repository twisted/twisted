from twisted.application import internet, service
from nevow import appserver

from twisted.vfs.backends import osfs
from twisted.internet.defer import gatherResults, Deferred
from nevow import livepage
from nufox import xul

class XULTKPage(xul.XULPage):

    def __init__(self, rootNode):
        self.rootNode = rootNode
        self.currNode = rootNode

        self.window = xul.Window(id="xul-window", height=400, width=400,
                                 title="XUL is Cool")

        v = xul.GroupBox(flex=1)
        self.box = v

        v.append(xul.Caption(label="Twisted XUL Sexy Fox Live VFS"))

        b = xul.Button(label="Up")
        b.addHandler('oncommand', self.up)
        v.append(b)

        self.idToChild = {}

        def listToTree(list):
            t = xul.Tree(flex=1)

            header = list[0]
            list = list[1:]
            th = xul.TreeCols()
            for cell in header:
                th.append(xul.TreeCol(flex=1, label=cell))
            t.append(th)

            tc = xul.TreeChildren()
            t.append(tc)
            return (t,tc)

        h = xul.HBox(flex=1)

        h.append(xul.Tree(flex=1))

        t,tc = listToTree([("Name", "Size", "Type", "Date Modified")])
        self.tree = t
        self.treeChildren = tc
        for row in [self._childToTreeRow(child)
                for name, child in self.currNode.children()
                if not name.startswith('.')]:
            self.addChild(row)
        t.addHandler('ondblclick', self.treeDblClick)
        h.append(t)

        v.append(h)

        self.window.append(v)

    def _childToTreeRow(self, child):

        from datetime import datetime
        from twisted.vfs.adapters import web
        import os.path
        from twisted.vfs import ivfs

        stat = child.getMetadata()
        size = "%s KB" % (stat['size']/1024,)
        mtime = datetime.fromtimestamp(stat['mtime'])

        if ivfs.IFileSystemContainer.providedBy(child):
            mimeType = 'folder'
        else:
            p, ext = os.path.splitext(child.name)
            mimeType = web.loadMimeTypes().get(ext, "text/html")

        return (child, child.name, size, mimeType, mtime)

    def addChild(self, row):
        child = row[0]
        row = row[1:]
        ti = xul.TreeItem()
        self.idToChild[str(ti.id)] = child
        tr = xul.TreeRow()
        for cell in row:
            tr.append(xul.TreeCell(label=str(cell)))
        ti.append(tr)
        self.treeChildren.append(ti)

    def getTreeSelection(self):
        def _cbTreeGetSelection(result):
            """result.split('.') - WTF livepage!"""
            result = [(self.idToChild[id], self.treeChildren.getChild(id))
                for id in result.split(',')]
            return result

        d = Deferred()
        getter = self.client.transient(lambda ctx, r: d.callback(r))
        self.client.send(getter(livepage.js.TreeGetSelected(self.tree.id)))
        d.addCallback(_cbTreeGetSelection)
        return d


    def updatePanel(self):
        self.treeChildren.remove(*self.treeChildren.children)
        for row in [self._childToTreeRow(child)
                for name, child in self.currNode.children()
                if not name.startswith('.')]:
            self.addChild(row)

    def treeDblClick(self):
        def _cbTreeDblClick(result):
            child = result[0][0]
            from twisted.vfs import ivfs
            if ivfs.IFileSystemContainer.providedBy(child):
                self.currNode = child
                self.updatePanel()

        self.getTreeSelection().addBoth(log).addCallback(_cbTreeDblClick)

    def up(self):
        self.currNode = self.currNode.parent
        self.updatePanel()

def log(r):
    print "LOGGING ",r
    return r

root = osfs.OSDirectory(realPath='../..')
application = service.Application('xulvfs')
webServer = internet.TCPServer(8080, appserver.NevowSite(XULTKPage(root)))
webServer.setServiceParent(application)
