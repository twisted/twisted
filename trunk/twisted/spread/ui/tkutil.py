
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""Utilities for building L{PB<twisted.spread.pb>} clients with L{Tkinter}.
"""
from Tkinter import *
from tkSimpleDialog import _QueryString
from tkFileDialog import _Dialog
from twisted.spread import pb
from twisted.internet import reactor
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

    @param title: the dialog title
    @param prompt: the label text
    @param **kw: see L{SimpleDialog} class

    @returns: a string
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

class ProgressBar:
    def __init__(self, master=None, orientation="horizontal",
                 min=0, max=100, width=100, height=18,
                 doLabel=1, appearance="sunken",
                 fillColor="blue", background="gray",
                 labelColor="yellow", labelFont="Verdana",
                 labelText="", labelFormat="%d%%",
                 value=0, bd=2):
        # preserve various values
        self.master=master
        self.orientation=orientation
        self.min=min
        self.max=max
        self.width=width
        self.height=height
        self.doLabel=doLabel
        self.fillColor=fillColor
        self.labelFont= labelFont
        self.labelColor=labelColor
        self.background=background
        self.labelText=labelText
        self.labelFormat=labelFormat
        self.value=value
        self.frame=Frame(master, relief=appearance, bd=bd)
        self.canvas=Canvas(self.frame, height=height, width=width, bd=0,
                           highlightthickness=0, background=background)
        self.scale=self.canvas.create_rectangle(0, 0, width, height,
                                                fill=fillColor)
        self.label=self.canvas.create_text(self.canvas.winfo_reqwidth() / 2,
                                           height / 2, text=labelText,
                                           anchor="c", fill=labelColor,
                                           font=self.labelFont)
        self.update()
        self.canvas.pack(side='top', fill='x', expand='no')

    def updateProgress(self, newValue, newMax=None):
        if newMax:
            self.max = newMax
        self.value = newValue
        self.update()

    def update(self):
        # Trim the values to be between min and max
        value=self.value
        if value > self.max:
            value = self.max
        if value < self.min:
            value = self.min
        # Adjust the rectangle
        if self.orientation == "horizontal":
            self.canvas.coords(self.scale, 0, 0,
              float(value) / self.max * self.width, self.height)
        else:
            self.canvas.coords(self.scale, 0,
                               self.height - (float(value) /
                                              self.max*self.height),
                               self.width, self.height)
        # Now update the colors
        self.canvas.itemconfig(self.scale, fill=self.fillColor)
        self.canvas.itemconfig(self.label, fill=self.labelColor)
        # And update the label
        if self.doLabel:
            if value:
                if value >= 0:
                    pvalue = int((float(value) / float(self.max)) *
                                   100.0)
                else:
                    pvalue = 0
                self.canvas.itemconfig(self.label, text=self.labelFormat
                                         % pvalue)
            else:
                self.canvas.itemconfig(self.label, text='')
        else:
            self.canvas.itemconfig(self.label, text=self.labelFormat %
                                   self.labelText)
        self.canvas.update_idletasks()

class DirectoryBrowser(_Dialog):
    command = "tk_chooseDirectory"

def askdirectory(**options):
    "Ask for a directory to save to."

    return apply(DirectoryBrowser, (), options).show()

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
    def __init__(self,
                 callback,
                 referenced = None,
                 initialUser = "guest",
                 initialPassword = "guest",
                 initialHostname = "localhost",
                 initialService  = "",
                 initialPortno   = pb.portno):
        Toplevel.__init__(self)
        version_label = Label(self,text="Twisted v%s" % copyright.version)
        self.pbReferenceable = referenced
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
        try:
            port = int(port)
        except:
            pass
        user = self.username.get()
        pswd = self.password.get()
        pb.connect(host, port, user, pswd, service,
                   client=self.pbReferenceable).addCallback(self.pbCallback).addErrback(
            self.couldNotConnect)

    def couldNotConnect(self,f):
        self.loginReport("could not connect:"+f.getErrorMessage())

if __name__=="__main__":
    root=Tk()
    o=CList(root,["Username","Online","Auto-Logon","Gateway"])
    o.pack()
    for i in range(0,16,4):
        o.insert(END,[i,i+1,i+2,i+3])
    mainloop()
