
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

from Tkinter import *
from tkSimpleDialog import _QueryString
from twisted.spread import pb
from twisted.internet import tcp
from twisted import copyright

import string

#normalFont = Font("-adobe-courier-medium-r-normal-*-*-120-*-*-m-*-iso8859-1")
#boldFont = Font("-adobe-courier-bold-r-normal-*-*-120-*-*-m-*-iso8859-1")
#errorFont = Font("-adobe-courier-medium-o-normal-*-*-120-*-*-m-*-iso8859-1")

class _QueryPassword(_QueryString):
    def body(self, master):

        w = Label(master, text=self.prompt, justify=LEFT)
        w.grid(row=0, padx=5, sticky=W)

        self.entry = Entry(master, name="entry",show="*")
        self.entry.grid(row=1, padx=5, sticky=W+E)

        if self.initialvalue:
            self.entry.insert(0, self.initialvalue)
            self.entry.select_range(0, END)

        return self.entry    

def askpassword(title, prompt, **kw):
    '''get a password from the user

    Arguments:

        title -- the dialog title
        prompt -- the label text
        **kw -- see SimpleDialog class

    Return value is a string
    '''
    d = apply(_QueryPassword, (title, prompt), kw)
    return d.result

def grid_setexpand(widget):
    cols,rows=widget.grid_size()
    for i in range(cols):
        widget.columnconfigure(i,weight=1)
    for i in range(rows):
        widget.rowconfigure(i,weight=1)

class CList(Frame):
    def __init__(self,parent,labels,disablesorting=0,**kw):
        Frame.__init__(self,parent)
        self.labels=labels
        self.lists=[]
        self.disablesorting=disablesorting
        kw["exportselection"]=0
        for i in range(len(labels)):
            b=Button(self,text=labels[i],anchor=W,height=1,pady=0)
            b.config(command=lambda s=self,i=i:s.setSort(i))
            b.grid(column=i,row=0,sticky=N+E+W)
            box=apply(Listbox,(self,),kw)
            box.grid(column=i,row=1,sticky=N+E+S+W)
            self.lists.append(box)
        grid_setexpand(self)
        self.rowconfigure(0,weight=0)
        self._callall("bind",'<Button-1>',self.Button1)
        self._callall("bind",'<B1-Motion>',self.Button1)
        self.bind('<Up>',self.UpKey)
        self.bind('<Down>',self.DownKey)
        self.sort=None

    def _callall(self,funcname,*args,**kw):
        rets=[]
        for l in self.lists:
            func=getattr(l,funcname)
            ret=apply(func,args,kw)
            if ret!=None: rets.append(ret)
        if rets: return rets
        
    def Button1(self,e):
        index=self.nearest(e.y)
        self.select_clear(0,END)
        self.select_set(index)
        self.activate(index)
        return "break"

    def UpKey(self,e):
        index=self.index(ACTIVE)
        if index:
            self.select_clear(0,END)
            self.select_set(index-1)
        return "break"

    def DownKey(self,e):
        index=self.index(ACTIVE)
        if index!=self.size()-1:
            self.select_clear(0,END)
            self.select_set(index+1)
        return "break"

    def setSort(self,index):
        if self.sort==None:
            self.sort=[index,1]
        elif self.sort[0]==index:
            self.sort[1]=-self.sort[1]
        else:
            self.sort=[index,1]
        self._sort()

    def _sort(self):
        if self.disablesorting:
            return
        if self.sort==None:
            return
        ind,direc=self.sort
        li=list(self.get(0,END))
        li.sort(lambda x,y,i=ind,d=direc:d*cmp(x[i],y[i]))
        self.delete(0,END)
        for l in li:
            self._insert(END,l)
    def activate(self,index):
        self._callall("activate",index)

   # def bbox(self,index):
   #     return self._callall("bbox",index)

    def curselection(self):
        return self.lists[0].curselection()

    def delete(self,*args):
        apply(self._callall,("delete",)+args)

    def get(self,*args):
        bad=apply(self._callall,("get",)+args)
        if len(args)==1:
            return bad
        ret=[] 
        for i in range(len(bad[0])):
            r=[]
            for j in range(len(bad)):
                r.append(bad[j][i])
            ret.append(r)
        return ret 

    def index(self,index):
        return self.lists[0].index(index)

    def insert(self,index,items):
        self._insert(index,items)        
        self._sort()

    def _insert(self,index,items):
        for i in range(len(items)):
            self.lists[i].insert(index,items[i])

    def nearest(self,y):
        return self.lists[0].nearest(y)

    def see(self,index):
        self._callall("see",index)

    def size(self):
        return self.lists[0].size()

    def selection_anchor(self,index):
        self._callall("selection_anchor",index)
   
    select_anchor=selection_anchor
   
    def selection_clear(self,*args):
        apply(self._callall,("selection_clear",)+args)
        
    select_clear=selection_clear
    
    def selection_includes(self,index):
        return self.lists[0].select_includes(index)
    
    select_includes=selection_includes

    def selection_set(self,*args):
        apply(self._callall,("selection_set",)+args)

    select_set=selection_set
    
    def xview(self,*args):
        if not args: return self.lists[0].xview()
        apply(self._callall,("xview",)+args)
        
    def yview(self,*args):
        if not args: return self.lists[0].yview()
        apply(self._callall,("yview",)+args)

class GenericLogin(Toplevel):
    def __init__(self,callback,buttons):
        Toplevel.__init__(self)
        self.callback=callback
        Label(self,text="Twisted v%s"%copyright.version).grid(column=0,row=0,columnspan=2)
        self.entries={}
        row=1
        for stuff in buttons:
            label,value=stuff[:2]
            if len(stuff)==3:
                dict=stuff[2]
            else: dict={}
            Label(self,text=label+": ").grid(column=0,row=row)
            e=apply(Entry,(self,),dict)
            e.grid(column=1,row=row)
            e.insert(0,value)
            self.entries[label]=e
            row=row+1
        Button(self,text="Login",command=self.doLogin).grid(column=0,row=row)
        Button(self,text="Cancel",command=self.close).grid(column=1,row=row)
        self.protocol('WM_DELETE_WINDOW',self.close)
    
    def close(self):
        self.tk.quit()
        self.destroy()

    def doLogin(self):
        values={}
        for k in self.entries.keys():
            values[string.lower(k)]=self.entries[k].get()
        self.callback(values)
        self.destroy()

class Login(Toplevel):
    def __init__(self, callback,
             referenced = None,
             initialUser = "guest",
                 initialPassword = "guest",
                 initialHostname = "localhost",
                 initialService  = "",
                 initialPortno   = pb.portno):
        Toplevel.__init__(self)
        version_label = Label(self,text="Twisted v%s" % copyright.version)
        self.pbReferenceable = referenceable
        self.pbCallback = callback
        # version_label.show()
        self.username = Entry(self)
        self.password = Entry(self,show='*')
        self.hostname = Entry(self)
        self.service  = Entry(self)
        self.port     = Entry(self)

        self.username.insert(0,initialUser)
        self.password.insert(0,initialPassword)
        self.service.insert(0,initialService)
        self.hostname.insert(0,initialHostname)
        self.port.insert(0,str(initialPortno))

        userlbl=Label(self,text="Username:")
        passlbl=Label(self,text="Password:")
        servicelbl=Label(self,text="Service:")
        hostlbl=Label(self,text="Hostname:")
        portlbl=Label(self,text="Port #:")
        self.logvar=StringVar()
        self.logvar.set("Protocol PB-%s"%pb.Broker.version)
        self.logstat  = Label(self,textvariable=self.logvar)
        self.okbutton = Button(self,text="Log In", command=self.login)

        version_label.grid(column=0,row=0,columnspan=2)
        z=0
        for i in [[userlbl,self.username],
                  [passlbl,self.password],
                  [hostlbl,self.hostname],
                  [servicelbl,self.service],
                  [portlbl,self.port]]:
            i[0].grid(column=0,row=z+1)
            i[1].grid(column=1,row=z+1)
            z = z+1

        self.logstat.grid(column=0,row=6,columnspan=2)
        self.okbutton.grid(column=0,row=7,columnspan=2) 

        self.protocol('WM_DELETE_WINDOW',self.tk.quit)

    def loginReset(self):
        self.logvar.set("Idle.")
        
    def loginReport(self, txt):
        self.logvar.set(txt)
        self.after(30000, self.loginReset)

    def login(self):
        host = self.hostname.get()
        port = self.port.get()
        service = self.service.get()
        # Maybe we're connecting to a unix socket, so don't make any
        # assumptions
        try:
            port = int(port)
        except:
            pass
        user = self.username.get()
        pswd = self.password.get()
        b = pb.Broker()
        self.broker = b
        b.requestIdentity(user, pswd,
                             callback   = self.gotIdentity,
                             errback    = self.couldNotConnect)
        b.notifyOnDisconnect(self.disconnected)
        tcp.Client(host, port, b)

    def gotIdentity(self,identity):
        identity.attach(self.service.get(),self.pbReferenceable,pbcallback=self.pbCallback)

    def couldNotConnect(self,*args):
        self.loginReport("could not connect.")

    def disconnected(self,*args):
        self.loginReport("disconnected from server.")

if __name__=="__main__":
    root=Tk()
    o=CList(root,["Username","Online","Auto-Logon","Gateway"])
    o.pack()
    for i in range(0,16,4):
        o.insert(END,[i,i+1,i+2,i+3])
    mainloop()
