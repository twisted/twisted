# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
What I want it to look like:

+- One
| \- Two
| |- Three
| |- Four
| +- Five
| | \- Six
| |- Seven
+- Eight
| \- Nine
"""

import os
from Tkinter import END, Listbox, Tk, Scrollbar, LEFT, BOTH, RIGHT, Y

class Node:
    def __init__(self):
        """
        Do whatever you want here.
        """
        self.item=None
    def getName(self):
        """
        Return the name of this node in the tree.
        """
        pass
    def isExpandable(self):
        """
        Return true if this node is expandable.
        """
        return len(self.getSubNodes())>0
    def getSubNodes(self):
        """
        Return the sub nodes of this node.
        """
        return []
    def gotDoubleClick(self):
        """
        Called when we are double clicked.
        """
        pass
    def updateMe(self):
        """
        Call me when something about me changes, so that my representation
        changes.
        """
        if self.item:
            self.item.update()

class FileNode(Node):
    def __init__(self,name):
        Node.__init__(self)
        self.name=name
    def getName(self):
        return os.path.basename(self.name)
    def isExpandable(self):
        return os.path.isdir(self.name)
    def getSubNodes(self):
        names=map(lambda x,n=self.name:os.path.join(n,x),os.listdir(self.name))
        return map(FileNode,names)

class TreeItem:
    def __init__(self,widget,parent,node):
        self.widget=widget
        self.node=node
        node.item=self
        if self.node.isExpandable():
            self.expand=0
        else:
            self.expand=None
        self.parent=parent
        if parent:
            self.level=self.parent.level+1
        else:
            self.level=0
        self.first=0 # gets set in Tree.expand()
        self.subitems=[]
    def __del__(self):
        del self.node
        del self.widget
    def __repr__(self):
        return "<Item for Node %s at level %s>"%(self.node.getName(),self.level)
    def render(self):
        """
        Override in a subclass.
        """
        raise NotImplementedError
    def update(self):
        self.widget.update(self)

class ListboxTreeItem(TreeItem):
    def render(self):
        start=self.level*"|    "
        if self.expand==None and not self.first:
            start=start+"|"
        elif self.expand==0:
            start=start+"L"
        elif self.expand==1:
            start=start+"+"
        else:
            start=start+"\\"
        r=[start+"- "+self.node.getName()]
        if self.expand:
            for i in self.subitems:
                r.extend(i.render())
        return r

class ListboxTree:
    def __init__(self,parent=None,**options):
        self.box=apply(Listbox,[parent],options)
        self.box.bind("<Double-1>",self.flip)
        self.roots=[]
        self.items=[]
    def pack(self,*args,**kw):
        """
        for packing.
        """
        apply(self.box.pack,args,kw)
    def grid(self,*args,**kw):
        """
        for gridding.
        """
        apply(self.box.grid,args,kw)
    def yview(self,*args,**kw):
        """
        for scrolling.
        """
        apply(self.box.yview,args,kw)
    def addRoot(self,node):
        r=ListboxTreeItem(self,None,node)
        self.roots.append(r)
        self.items.append(r)
        self.box.insert(END,r.render()[0])
        return r
    def curselection(self):
        c=self.box.curselection()
        if not c: return
        return self.items[int(c[0])]
    def flip(self,*foo):
        if not self.box.curselection(): return
        item=self.items[int(self.box.curselection()[0])]
        if item.expand==None: return
        if not item.expand:
            self.expand(item)
        else:
            self.close(item)
        item.node.gotDoubleClick()
    def expand(self,item):
        if item.expand or item.expand==None: return
        item.expand=1
        item.subitems=map(lambda x,i=item,s=self:ListboxTreeItem(s,i,x),item.node.getSubNodes())
        if item.subitems:
            item.subitems[0].first=1
        i=self.items.index(item)
        self.items,after=self.items[:i+1],self.items[i+1:]
        self.items=self.items+item.subitems+after
        c=self.items.index(item)
        self.box.delete(c)
        r=item.render()
        for i in r:
            self.box.insert(c,i)
            c=c+1
    def close(self,item):
        if not item.expand: return
        item.expand=0
        length=len(item.subitems)
        for i in item.subitems:
            self.close(i)
        c=self.items.index(item)
        del self.items[c+1:c+1+length]
        for i in range(length+1):
            self.box.delete(c)
        self.box.insert(c,item.render()[0])
    def remove(self,item):
        if item.expand:
            self.close(item)
        c=self.items.index(item)
        del self.items[c]
        if item.parent:
            item.parent.subitems.remove(item)
        self.box.delete(c)
    def update(self,item):
        if item.expand==None:
            c=self.items.index(item)
            self.box.delete(c)
            self.box.insert(c,item.render()[0])
        elif item.expand:
            self.close(item)
            self.expand(item)

if __name__=="__main__":
    tk=Tk()
    s=Scrollbar()
    t=ListboxTree(tk,yscrollcommand=s.set)
    t.pack(side=LEFT,fill=BOTH)
    s.config(command=t.yview)
    s.pack(side=RIGHT,fill=Y)
    t.addRoot(FileNode("C:/"))
    #mainloop()
