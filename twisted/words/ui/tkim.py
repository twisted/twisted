from Tkinter import *
from twisted.internet import tkinternet #, tcp
from twisted.spread.ui import tkutil
from twisted.words.ui import im2, gateways
#from twisted.protocols import telnet
import time, os, string
import sys

def timeheader():
    y,mon,d,h,min,sec,ig,no,re=time.localtime(time.time())
    return "%02i:%02i:%02i"%(h,min,sec)

class AddContact(Toplevel):
    def __init__(self,im,*args,**kw):
        apply(Toplevel.__init__,(self,)+args,kw)
        self.im=im
        self.title("Add Contact - Instance Messenger")
        Label(self,text="Contact Name?").grid(column=0,row=0)
        self.contact=Entry(self)
        self.contact.grid(column=1,row=0)
        self.contact.bind('<Return>',self.addContact)
        self.gates=Listbox(self)
        self.gates.grid(column=0,row=1,columnspan=2)
        for k in self.im.gateways.keys():
            self.gates.insert(END,k)
        Button(self,text="Add Contact",command=self.addContact).grid(column=0,row=2)
        Button(self,text="Cancel",command=self.destroy).grid(column=1,row=2)
        self.protocol('WM_DELETE_WINDOW',self.destroy)
        tkutil.grid_setexpand(self)

    def addContact(self,*args):
        contact=self.contact.get()
        gatewayname=self.gates.get(ACTIVE)
        if contact:
            self.im.addContact(self.im.gateways[gatewayname],contact)
            self.destroy()

class StartConversation(Toplevel):
    def __init__(self,im,*args,**kw):
        apply(Toplevel.__init__,(self,)+args,kw)
        self.im=im
        self.title("Start Conversation - Instance Messenger")
        Label(self,text="Start Conversation With?").grid(column=0,row=0)
        self.contact=Entry(self)
        self.contact.grid(column=1,row=0)
        self.contact.bind('<Return>',self.startConvo)
        self.gates=Listbox(self)
        self.gates.grid(column=0,row=1,columnspan=2)
        for k in self.im.gateways.keys():
            self.gates.insert(END,k)
        Button(self,text="Start Conversation",command=self.startConvo).grid(column=0,row=2)
        Button(self,text="Cancel",command=self.destroy).grid(column=1,row=2)
        self.protocol('WM_DELETE_WINDOW',self.destroy)
        tkutil.grid_setexpand(self)

    def startConvo(self,*args):
        contact=self.contact.get()
        gatewayname=self.gates.get(ACTIVE)
        if contact:
            self.im.conversationWith(self.im.gateways[gatewayname],contact)
            self.destroy()

class JoinGroup(Toplevel):
    def __init__(self,im,*args,**kw):
        apply(Toplevel.__init__,(self,)+args,kw)
        self.im=im
        self.title("Join Group - Instance Messenger")
        Label(self,text="Group Name?").grid(column=0,row=0)
        self.group=Entry(self)
        self.group.grid(column=1,row=0)
        self.group.bind('<Return>',self.joinGroup)
        self.gates=Listbox(self)
        self.gates.grid(column=0,row=1,columnspan=2)
        for k in self.im.gateways.keys():
            self.gates.insert(END,k)
        Button(self,text="Join Group",command=self.joinGroup).grid(column=0,row=2)
        Button(self,text="Cancel",command=self.destroy).grid(column=1,row=2)
        tkutil.grid_setexpand(self)
        self.protocol('WM_DELETE_WINDOW',self.destroy)

    def joinGroup(self,*args):
        group=self.group.get()
        gatewayname=self.gates.get(ACTIVE)
        if group:
            self.im.joinGroup(self.im.gateways[gatewayname],group)
            self.destroy()


class Conversation(Toplevel):
    def __init__(self, im, gateway, target, **params):
        apply(Toplevel.__init__, (self,), params)

        self.title("%s - %s - Instance Messenger" % (target, gateway.name))
        self.im=im
        self.gateway=gateway
        self.target=target

        self.out = Text(self, height=1, width=1, wrap='word')
        self.out.grid(column=0, row=0, sticky='nesw')
        sb = Scrollbar(self,  command=self.out.yview, orient='v')
        self.out.config(yscrollcommand = sb.set)
        self.out.bind("<Key>",lambda x:"break")
        self.out.bind("<Button-3>",self.copy)
        sb.grid(column=1, row=0, sticky='ns')

        self.input = Text(self, height=1, width=1)
        self.input.grid(column=0, columnspan=2, row=1, sticky='nesw')
        self.input.bind("<Return>",lambda e,s=self:s.sendMessage())
        self.input.focus()

        frame = Frame(self)
        frame.grid(column=0, columnspan=2, row=2)
        extras = Button(frame, text='%s Extras' % gateway.protocol)
        extras.grid(column=1, row=1)
        extras.bind("<ButtonRelease-1>", self.showExtrasMenu)
        send = Button(frame, command=self.sendMessage, text='Send')
        send.grid(column=2, row=1)
        leave = Button(frame, command=self.endConversation, text='Leave')
        leave.grid(column=3, row=1)

        self.grid_rowconfigure(0, weight=1, minsize=112)
        #self.grid_rowconfigure(1, weight=0, minsize=49)
        #self.grid_rowconfigure(2, weight=0, minsize=30)
        self.grid_columnconfigure(0, weight=1, minsize=286)
        #self.grid_columnconfigure(1, weight=0, minsize=2)
        #frame.grid_rowconfigure(0, weight=0, minsize=30)
        frame.grid_columnconfigure(0, weight=1, minsize=5)
        frame.grid_columnconfigure(1, weight=1, minsize=30)
        frame.grid_columnconfigure(2, weight=1, minsize=30)

        self.protocol('WM_DELETE_WINDOW', self.endConversation)

    def blink(self):
        return
#        self.deiconify()
#        self.input.focus()

    def copy(self,event):
        text=self.out.selection_get()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
        return "break"

    def showExtrasMenu(self, e):
        m=Menu()
        extras=gateways.__gateways__[self.gateway.protocol].conversationExtras
        for name,func in extras:
            m.add_command(label=name,command=lambda s=self,f=func:s.runExtra(f))
        m.post(e.x_root,e.y_root)

    def runExtra(self,f):
        i=self.input.get("1.0",END)[:-1]
        s=f(self.im,self.gateway,self.target,i)
        self.input.delete("1.0",END)
        self.input.insert(END,s)

    def sendMessage(self):
        message=self.input.get("1.0",END)[:-1]
        if message:
            self.out.insert(END,"\n%s <%s> %s" % (timeheader(), self.gateway.username, message))
            self.out.see(END)
            self.im.directMessage(self.gateway, self.target, message)
            self.input.delete("1.0",END)
        return "break"

    def endConversation(self):
        self.destroy()
        self.im.endConversation(self.gateway, self.target)

    def messageReceived(self, message):
        self.out.insert(END,"\n%s <%s> %s" % (timeheader(), self.target, message))
        self.out.see(END)
        self.blink()

    def changeName(self, newName):
        self.out.insert(END,"\n%s %s changed name to %s." % (timeheader(), self.target, newName))
        self.out.see(END)
        self.target=newName

    def changeStatus(self, newStatus):
        self.out.insert(END,"\n%s %s is now %s." % (timeheader(), self.target, newStatus))
        self.out.see(END)

class ContactList(Toplevel):
    def __init__(self,im,*args,**kw):
        apply(Toplevel.__init__,(self,)+args,kw)

        self.im=im

        menu=Menu(self)
        self.config(menu=menu)
        myim=Menu(menu)
        menu.add_cascade(label="My IM",menu=myim)
        statuschange=Menu(myim)
        myim.add_cascade(label="Change Status",menu=statuschange)
        for k in im2.STATUSES:
            statuschange.add_command(label=k,command=lambda i=self.im,s=k:i.changeStatus(s))
        myim.add_command(label="Account Manager...",command=lambda i=self.im:i.am.deiconify())
        myim.add_command(label="Start Conversation...",command=lambda i=self.im:StartConversation(i))
#        myim.add_command(label="__reload__",command=self.reload)

        sb=Scrollbar(self)
        self.list=tkutil.CList(self,["Gateway","Username","Status"],height=2,yscrollcommand=sb.set)
        self.list.grid(column=0,row=0,sticky=N+E+S+W)
        sb.grid(column=1,row=0,sticky=N+S)
        sb.config(command=self.list.yview)

        f=Frame(self)
        Button(f,text="Add Contact",command=self.addContact).grid(column=0,row=1)
        Button(f,text="Remove Contact",command=self.removeContact).grid(column=1,row=1)
        Button(f,text="Send Message",command=self.sendMessage).grid(column=2,row=1)
        Button(f,text="Join Group",command=self.joinGroup).grid(column=3,row=1)
        b=Button(f,text="Extras")
        b.grid(column=4,row=1,sticky=N+E+S+W)
        b.bind('<ButtonRelease-1>',self.showExtrasMenu)
        f.grid(column=0,row=1,columnspan=2,sticky=E+S+W)

        self.title("Instance Messenger")
        self.protocol("WM_DELETE_WINDOW",self.close)
        tkutil.grid_setexpand(self)
        self.columnconfigure(0,weight=1)
        self.columnconfigure(1,weight=0)
        self.rowconfigure(1,weight=0)

    def close(self):
        self.tk.quit()
        self.destroy()

    def reload(self):
        m=sys.modules
        for k,v in m.items():
            if k not in ['twisted.internet.main','twisted.internet.tkinternet'] and v and k[:8]=='twisted.':
                reload(v)
                print 'reloaded %s'%k

    def addContact(self):
        AddContact(self.im)

    def removeContact(self):
        gatewayname,contact,state=self.list.get(ACTIVE)
        self.list.delete(ACTIVE)
        self.im.removeContact(self.im.gateways[gatewayname],contact)

    def removeGateway(self,gateway):
        users=self.list.get(0,END)
        d=[]
        for u in range(len(users)):
            if users[u][0]==gateway.name:
                d.insert(0,u)
        for u in d:
            self.list.delete(u)

    def changeContactStatus(self,gateway,contact,status):
        users=self.list.get(0,END)
        row=END
        for u in range(len(users)):
            if users[u][0]==gateway.name and users[u][1]==contact:
                row=u
                self.list.delete(row)
                break
        self.list.insert(row,[gateway.name,contact,status])

    def changeContactName(self,gateway,contact,newName):
        users=self.list.get(0,END)
        row=END
        for u in range(len(users)):
            if users[u][0]==gateway.name and users[u][1]==contact:
                row=u
                self.list.delete(row)
                self.list.insert(row,[gateway.name,newName,users[u][2]])

    def sendMessage(self):
        gatewayname,user,state=self.list.get(ACTIVE)
        try:
            self.im.conversationWith(self.im.gateways[gatewayname],user)
        except KeyError:
            pass

    def joinGroup(self):
        JoinGroup(self.im)

    def showExtrasMenu(self,e):
        m=Menu()
        for g in self.im.gateways.values():
            subm=Menu(m)
            extras=gateways.__gateways__[g.protocol].contactListExtras
            for name,func in extras:
                subm.add_command(label=name,command=lambda s=self,g=g,f=func:s.runExtra(g,f))
            m.add_cascade(label=g.name,menu=subm)
        m.post(e.x_root,e.y_root)

    def runExtra(self,gateway,func):
        gatewayname,user,state=self.list.get(ACTIVE)
        if gatewayname!=gateway.name:
            user=None
            state=None
        func(self.im,gateway,user,state)

class GroupSession(Toplevel):
    def __init__(self, im, name, gateway, **params):
        apply(Toplevel.__init__, (self,), params)

        self.im=im
        self.name=name
        self.gateway=gateway

        self.title("%s - %s - Instance Messenger" % (self.name, self.gateway.name))

        self.out = Text(self, height=1, wrap='word')
        self.out.grid(column=0, row=0, sticky='nesw')
        self.out.bind("<Key>",lambda x:"break")
        self.out.bind("<Button-3>",self.copy)
        out_scroll=Scrollbar(self, command=self.out.yview, orient='v')
        out_scroll.grid(column=1, row=0, sticky='ns')
        self.out.config(yscrollcommand=out_scroll.set)
        self.out.tag_configure("hilite",foreground="blue")

        self.userlist = Listbox(self)
        self.userlist.grid(column=2, row=0, sticky='nesw')
        user_scroll = Scrollbar(self, command=self.userlist.yview, orient='v')
        user_scroll.grid(column=3, row=0, sticky='ns')
        self.userlist.config(yscrollcommand=user_scroll.set)

        self.input = Text(self, height=1, width=1)
        self.input.grid(column=0, row=1, sticky='nesw', columnspan=4)
        self.input.bind("<Return>", self.sendMessage)
        self.input.bind("<Tab>", self.nickComplete)
        self.input.focus()

        frame = Frame(self)
        frame.grid(column=0, columnspan=4, row=2)
        send=Button(frame, command=self.sendMessage, text='Send')
        send.grid(column=0, row=0, sticky='nesw')
        leave = Button(frame, command=self.leaveGroup, text='Leave')
        leave.grid(column=1, row=0, sticky='nesw')
        extras = Button(frame, text='%s Extras' % self.gateway.protocol)
        extras.grid(column=2, row=0, sticky='nesw')
        extras.bind("<ButtonRelease-1>", self.showExtrasMenu)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.protocol('WM_DELETE_WINDOW',self.leaveGroup)

        self.im.getGroupMembers(self.gateway, self.name)

    def _sortlist(self):
        l=list(self.userlist.get(0,END))
        l.sort(lambda x,y:cmp(string.lower(x),string.lower(y)))
        self.userlist.delete(0,END)
        for u in l:
            self.userlist.insert(END,u)

    def blink(self):
        return
#        self.deiconify()
#        self.input.focus()

    def copy(self,event):
        text=self.out.selection_get()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
        return "break"

    def sendMessage(self,event=None):
        message=self.input.get("1.0",END)[:-1]
        if message:
            self.out.insert(END,"\n<<%s>> %s" % (self.gateway.username, message))
            self.out.see(END)
            self.im.groupMessage(self.gateway, self.name, message)
            self.input.delete("1.0",END)
        return "break"

    def leaveGroup(self):
        self.destroy()
        self.im.leaveGroup(self.gateway,self.name)

    def showExtrasMenu(self,e):
        m=Menu()
        extras=gateways.__gateways__[self.gateway.protocol].groupExtras
        for name,func in extras:
            m.add_command(label=name,command=lambda s=self,f=func:s.runExtra(f))
        m.post(e.x_root,e.y_root)

    def runExtra(self,f):
        i=self.input.get("1.0",END)[:-1]
        items = self.userlist.curselection()
        try:
            items = map(string.atoi, items)
        except ValueError: pass
        items = map(lambda i,d=self.userlist.get: d(i), items)
        s=f(self.im,self.gateway,self.name,i,items)
        self.input.delete("1.0",END)
        self.input.insert(END,s)

    def receiveGroupMembers(self, members):
        for m in members:
            self.userlist.insert(END,m)
        self._sortlist()

    def receiveGroupMessage(self, member, message):
        tags=[]
        if string.find(message,self.gateway.username)!=-1:
            tags.append("hilite")
        self.out.insert(END, "\n<%s> %s" % (member, message),tuple(tags))
        self.out.see(END)
        self.blink()

    def memberJoined(self, member):
        self.out.insert(END, "\n%s joined!" % member)
        self.out.see(END)
        self.userlist.insert(END,member)
        self._sortlist()
        self.blink()

    def memberLeft(self, member):
        self.out.insert(END, "\n%s left!" % member)
        self.out.see(END)
        users=list(self.userlist.get(0,END))
        if member in users:
            i=users.index(member)
            self.userlist.delete(i)
        self.blink()

    def changeMemberName(self, member, newName):
        users=list(self.userlist.get(0,END))
        if member in users:
            self.out.insert(END,"\n%s changed name to %s." % (member, newName))
            self.out.see(END)
            i=users.index(member)
            self.userlist.delete(i)
            self.userlist.insert(END,newName)
            self._sortlist()
        else:
            print "user %s not in group %s!" % (member, self.name)

    def nickComplete(self, e):
        start=self.input.get("1.0",END)[:-1]
        lstart=string.lower(start)
        l=list(self.userlist.get(0,END))
        ll=map(string.lower,l)
        if lstart in ll:
            i=ll.index(lstart)
            self.input.delete("1.0",END)
            self.input.insert(END,l[i]+": ")
            return "break"
        matches=[]
        for u in ll:
            if len(u)>len(lstart) and u[:len(lstart)]==lstart:
                matches.append(u)
        if len(matches)==1:
            i=ll.index(matches[0])
            self.input.delete("1.0",END)
            self.input.insert(END,l[i]+": ")
            return "break"
        elif matches==[]:
            return "break"
        longestmatch=matches[0]
        for u in matches:
            if len(u)>len(longestmatch):
                u=u[:len(longestmatch)]
            c=0
            while c<len(longestmatch) and longestmatch[c]==u[c]:
                c=c+1
            longestmatch=longestmatch[:c]
        self.input.delete("1.0",END)
        self.input.insert(END,longestmatch)
        self.out.insert(END,"\n")
        for u in matches:
            i=ll.index(u)
            self.out.insert(END,"[%s] "%l[i])
        return "break"

class ErrorWindow(Toplevel):
    def __init__(self,error,message,*args,**kw):
        apply(Toplevel.__init__,(self,)+args,kw)
        self.title(error)
        f=Frame(self)
        Label(f,text=message).grid()
        f.pack()
        self.protocol("WM_DELETE_WINDOW",self.destroy)

class ChooseGateway(Toplevel):
    def __init__(self,callback,**kw):
        apply(Toplevel.__init__,(self,),kw)
        self.callback=callback
        self.title("Choose a Gateway - Instance Messenger")
        self.gateways=[]
        self.list=Listbox(self)
        reload(gateways)
        for k in gateways.__gateways__.keys():
            self.gateways.append(k)
            self.list.insert(END,gateways.__gateways__[k].shortName)
        self.list.grid(column=0,row=0,columnspan=2,sticky=N+E+S+W)
        Button(self,text="OK",command=self.choose).grid(column=0,row=1,sticky=E+S)
        Button(self,text="Cancel",command=self.destroy).grid(column=1,row=1,sticky=E+S)
        self.protocol('WM_DELETE_WINDOW',self.destroy)

    def choose(self):
        index=self.list.index(ACTIVE)
        self.callback(self.gateways[index])
        self.destroy()

class AddAccount(Toplevel):
    def __init__(self,gateway,acctman,**kw):
        apply(Toplevel.__init__,(self,),kw)
        self.gateway=gateway
        self.acctman=acctman
        self.title("Add %s Account - Instance Messenger"%gateway)
        self.options={}
        useroptions=gateways.__gateways__[gateway].loginOptions
        r=0
        for title,key,default in useroptions:
            dict={}
            if len(key)>3 and key[:4]=="pass":
                dict["show"]="*"
            Label(self,text=title+": ").grid(column=0,row=r,sticky=W+N)
            entry=apply(Entry,(self,),dict)
            entry.insert(0,default)
            entry.grid(column=1,row=r,sticky=E+N)
            self.options[key]=entry
            r=r+1
        self.autologon=IntVar()
        Checkbutton(self,text="Auto Logon?",variable=self.autologon).grid(column=0,row=r,columnspan=2,sticky=W+E+N)
        r=r+1
        self.savepass=IntVar()
        Checkbutton(self,text="Save Password?",variable=self.savepass).grid(column=0,row=r,columnspan=2,sticky=W+E+N)
        r=r+1
        Button(self,text="OK",command=self.addAccount).grid(column=0,row=r,sticky=N+W)
        Button(self,text="Cancel",command=self.destroy).grid(column=1,row=r,sticky=E+W)
        self.protocol("WM_DELETE_WINDOW",self.destroy)

    def addAccount(self):
        o={}
        for k in self.options.keys():
            o[k]=self.options[k].get()
        auto=self.autologon.get()
        savepass=self.savepass.get()
        self.acctman._addaccount(im2.Account(self.gateway,o,auto,savepass))
        self.destroy()

class ModifyAccount(Toplevel):
    def __init__(self,acctman,account,**kw):
        apply(Toplevel.__init__,(self,),kw)
        self.acctman=acctman
        self.account=account
        self.title("Modify %s Account - Instance Messenger"%account.gatewayname)
        self.options={}
        useroptions=gateways.__gateways__[account.gatewayname].loginOptions
        r=0
        for title,key,default in useroptions:
            dict={}
            if len(key)>3 and key[:4]=="pass":
                dict["show"]="*"
            Label(self,text=title+": ").grid(column=0,row=r,sticky=W+N)
            if key!="username":
                entry=apply(Entry,(self,),dict)
                try:
                    default=account.options[key]
                except KeyError:
                    default=""
                entry.insert(0,default)
                entry.grid(column=1,row=r,sticky=E+N)
                self.options[key]=entry
            else:
                Label(self,text=account.options[key],relief=SUNKEN,anchor=W).grid(column=1,row=r,sticky=W+E+N)
            r=r+1
        self.autologon=IntVar()
        self.autologon.set(account.autologon)
        Checkbutton(self,text="Auto Logon?",variable=self.autologon).grid(column=0,row=r,columnspan=2,sticky=W+E+N)
        r=r+1
        self.savepass=IntVar()
        self.savepass.set(account.savepass)
        Checkbutton(self,text="Save Password?",variable=self.savepass).grid(column=0,row=r,columnspan=2,sticky=W+E+N)
        r=r+1
        Button(self,text="OK",command=self.modifyAccount).grid(column=0,row=r,sticky=N+W)
        Button(self,text="Cancel",command=self.destroy).grid(column=1,row=r,sticky=E+W)
        self.protocol("WM_DELETE_WINDOW",self.destroy)

    def modifyAccount(self):
        o={}
        for k in self.options.keys():
            self.account.options[k]=self.options[k].get()
        self.account.autologon=self.autologon.get()
        self.account.savepass=self.savepass.get()
        self.acctman._modifyaccount(self.account)
        self.destroy()

class AccountManager(Toplevel):
    def __init__(self,im,*args,**kw):
        apply(Toplevel.__init__,(self,)+args,kw)
        self.title("Account Manager - Instance Messenger")
        self.im=im
        self.accounts=[]
        sb=Scrollbar(self)
        self.list=tkutil.CList(self,["Username    ","Online","Auto-Logon","Gateway    "],yscrollcommand=sb.set)
        sb.config(command=self.list.yview)
        self.list.grid(column=0,row=0,sticky=N+E+S+W)
        sb.grid(column=1,row=0,sticky=N+S+E)
        f=Frame(self)
        Button(f,text="Add",command=self.addAccount).grid(column=0,row=0,sticky=N+E+S+W)
        Button(f,text="Modify",command=self.modifyAccount).grid(column=1,row=0,sticky=N+E+S+W)
        Button(f,text="Log On/Off",command=self.logOnOff).grid(column=2,row=0,sticky=N+E+S+W)
        Button(f,text="Delete",command=self.deleteAccount).grid(column=3,row=0,sticky=N+E+S+W)
        tkutil.grid_setexpand(f)
        f.grid(column=0,row=1,rowspan=2,sticky=S+E+W)
        self.rowconfigure(0,weight=1)
        self.columnconfigure(0,weight=1)
        self.protocol("WM_DELETE_WINDOW",self.close)

        self.im.addCallback(None,"attached",self.handleAttached)
        self.im.addCallback(None,"detached",self.handleDetached)

    def close(self):
        self.withdraw()
        if self.im.cl==None: self.tk.quit()

    def getState(self):
        return self.accounts

    def loadState(self,state):
        autos=[]
        for account in state:
            self._addaccount(account)
            if account.autologon: # autologon
                autos.append(account)
        for account in autos:
            self.logonAccount(account)

    def addAccount(self):
        ChooseGateway(callback=lambda g,s=self:AddAccount(g,s))

    def _addaccount(self,account,online="False"):
        self.accounts.append(account)
        auto=account.autologon and "True" or "False"
        self.list.insert(END,(account.options["username"],online,auto,\
                              account.gatewayname))

    def modifyAccount(self):
        index=self.list.index(ACTIVE)
        account=self.accounts[index]
        ModifyAccount(self,account)

    def _modifyaccount(self,account,online=None):
        # assumes username is an option
        #self.accounts[name]=account
        i=self.accounts.index(account)
        username,foo,bar,gateway=self.list.get(i)
        auto=account.autologon and "True" or "False"
        online=online or foo
        self.list.delete(i)
        self.list.insert(i,[username,online,auto,gateway])

    def logOnOff(self):
        index=self.list.index(ACTIVE)
        account=self.accounts[index]
        username,online,auto,gateway=self.list.get(index)
        if online=="False":
            self.logonAccount(account)
        else:
            self.logoffAccount(account)

    def logonAccount(self,account):
        self._modifyaccount(account,"Attempting")
        missing=im2.logonAccount(self.im,account)
        while missing:
            for foo,key,bar in missing:
                if key[:4]=="pass":
                    # XXX this hangs on windows
                    value=tkutil.askpassword("Enter %s for %s"%(foo, \
                                    account.options["username"]), foo+": ")
                else:
                    value=tkSimpleDialog.askstring("Enter %s for %s"%(foo, \
                                    account.options["username"]), foo+": ")
                account.options[key]=value
            missing=im2.logonAccount(self.im,account)

    def logoffAccount(self,account):
        im2.logoffAccount(self.im,account)

    def deleteAccount(self):
        index=self.list.index(ACTIVE)
        self.list.delete(index)
        account=self.accounts[index]
        self.logoffAccount(account)
        del self.accounts[index]

    def handleAttached(self,im,gateway,event):
        for account in self.accounts:
            if account.gatewayname==gateway.protocol and account.options["username"]==gateway.logonUsername:
                self._modifyaccount(account,"True")

    def handleDetached(self,im,gateway,event):
        if im.cl!=None: im.cl.removeGateway(gateway)
        for account in self.accounts:
            if account.gatewayname==gateway.protocol and account.options["username"]==gateway.logonUsername:
                self._modifyaccount(account,"False")

def handleError(im,gateway,event,code,message):
    strgate=str(gateway)
    for key,value in im.conversations.items():
        if key[:len(strgate)]==strgate:
            value.destroy()
            im.endConversation(gateway,value.target)
    for key,value in im.groups.items():
        if key[:len(strgate)]==strgate:
            value.destroy()
            del im.groups[strgate+value.name]

def main():
    root=Tk()
    root.withdraw()
    tkinternet.install(root)
    im=im2.InstanceMessenger(Conversation, ContactList, GroupSession, ErrorWindow)
    im.am=AccountManager(im)
    path=os.path.expanduser("~"+os.sep+".imsaved")
    try:
        f=open(path,"r")
        im.am.loadState(im2.getState(f))
        f.close()
    except IOError:
        pass
    im.addCallback(None,"error",handleError)
#    t=telnet.ShellFactory()
#    import __main__
#    t.namespace=__main__.__dict__
#    t.namespace['im']=im
#    tcp.Port(10023,t).startListening()
    mainloop()
    for g in im.gateways.values():
        g.loseConnection()
    tkinternet.stop()
    f=open(path,"w")
    im2.saveState(f,im.am.getState())

if __name__=="__main__": main()
