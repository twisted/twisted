
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
import tkSimpleDialog
from twisted.spread.ui import tkutil
from twisted.internet import tkinternet
from twisted.words.ui import im2
from twisted.words.ui import gateways
import time
import string

class ErrorWindow(Toplevel):
    def __init__(self,code,message,*args,**kw):
        apply(Toplevel.__init__,(self,)+args,kw)
        self.title("Error %s"%code)
        f=Frame(self)
        Label(f,text=message).grid()
        f.pack()
        self.protocol("WM_DELETE_WINDOW",self.destroy)
        
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
            self.im.addContact(gatewayname,contact)
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
            self.im.joinGroup(gatewayname,group)
            self.destroy()

class GroupSession(Toplevel):
    def __init__(self,name,im,gatewayname,*args,**kw):
        apply(Toplevel.__init__,(self,)+args,kw)
        self.title("%s - Instance Messenger"%name)
        self.name=name
        self.im=im
        self.gatewayname=gatewayname
        self.output=Text(self,height=3,wrap=WORD,state=DISABLED,bg="white")
        self.output.grid(column=0,row=0,sticky=N+E+S+W)
        sb=Scrollbar(self)
        self.output.config(yscrollcommand=sb.set)
        sb.config(command=self.output.yview)
        sb.grid(column=1,row=0,sticky=N+S)
        self.list=Listbox(self,height=2,bg="white")
        sb=Scrollbar(self,command=self.list.yview)
        self.list.config(yscrollcommand=sb.set)
        self.list.grid(column=2,row=0,sticky=N+E+S+W)
        sb.grid(column=3,row=0,sticky=N+S)
        self.input=Text(self,height=1,wrap=WORD,bg="white")
        self.input.grid(column=0,row=1,columnspan=4,sticky=N+E+S+W)
        self.input.bind('<Return>',self.say)
        self.protocol('WM_DELETE_WINDOW',self.close)
        f=Frame(self)
        Button(f,text="Send",command=self.say).grid(column=0,row=0,sticky=N+E+S+W)
        Button(f,text="Leave",command=self.close).grid(column=1,row=0,sticky=N+E+S+W)
        f.grid(column=0,row=2,columnspan=4)
        tkutil.grid_setexpand(self)
        self.rowconfigure(0,weight=3)
        self.columnconfigure(1,weight=0)
        self.columnconfigure(3,weight=0)
        self.rowconfigure(2,weight=0)
        self._nolist=1
        self.im.getGroupMembers(self.gatewayname,self.name)

    def close(self):
        self.im.leaveGroup(self.gatewayname,self.name)
        self.destroy()
    
    def _out(self,text):
        self.output.config(state=NORMAL)
        #self.outputhtml.feed(text)
        self.output.insert(END,text)
        self.output.see(END)
        self.output.config(state=DISABLED)
    
    def receiveGroupMembers(self,list):
        self._nolist=0
        for m in list:
            self.list.insert(END,m)
    
    def displayMessage(self,user,message):
        self._out("<%s> %s\n"%(user,message))
    
    def memberJoined(self,user):
        self._out("%s joined!\n"%user)
        if not self._nolist:self.list.insert(END,user)
    
    def memberLeft(self,user):
        self._out("%s left!\n"%user)
        if not self._nolist:
            users=list(self.list.get(0,END))
            i=users.index(user)
            self.list.delete(i)
    
    def say(self,*args):
        text=self.input.get("1.0",END)[:-1]
        if not text: return
        self.input.delete("1.0",END)
        self.im.groupMessage(self.gatewayname,self.name,text)
        self._out("<<%s>> %s\n"%(self.im.gateways[self.gatewayname].username,text))
        return "break"
        
class Conversation(Toplevel):
    def __init__(self,im,gatewayname,contact,*args,**kw):
        apply(Toplevel.__init__,(self,)+args,kw)
        self.contact=contact
        self.im=im
        self.gatewayname=gatewayname
        self.title("%s - Instance Messenger"%contact)
        self.output=Text(self,height=3,width=10,wrap=WORD,bg="white")
        self.input=Text(self,height=1,width=10,wrap=WORD,bg="white") 
        self.bar=Scrollbar(self)
        self.output.grid(column=0,row=0,sticky=N+E+S+W)
        self.bar.grid(column=1,row=0,sticky=N+S)
        self.output["state"]=DISABLED
        self.output["yscrollcommand"]=self.bar.set
        self.bar["command"]=self.output.yview
        self.input.grid(column=0,row=1,columnspan=2,sticky=N+E+S+W)
        self.input.bind('<Return>',self.say)
        #self.pack()
        self.protocol("WM_DELETE_WINDOW",self.close)
        tkutil.grid_setexpand(self)
        self.rowconfigure(0,weight=3)
        self.columnconfigure(1,weight=0)
    
    def close(self):
        del self.im.conversations[self.gatewayname+self.contact]
        self.destroy()
    
    def _addtext(self,text):
        self.output["state"]=NORMAL
        #self.outputhtml.feed(text)
        self.output.insert(END,text)
        self.output["state"]=DISABLED
    
    def messageReceived(self,message,sender=None):
        y,mon,d,h,min,sec,ig,no,re=time.localtime(time.time())
        text="%s:%s:%s %s: %s\n"%(h,min,sec,sender or self.contact,message)
        self._addtext(text)
        self.output.see(END)
    
    def say(self,event):
        message=self.input.get('1.0',END)[:-1]
        self.input.delete('1.0',END)
        if message:
            self.messageReceived(message,self.im.gateways[self.gatewayname].username)
            self.im.directMessage(self.gatewayname,self.contact,message)
        return "break" # don't put the newline in

class ContactList(Toplevel):
    def __init__(self,im,*args,**kw):
        apply(Toplevel.__init__,(self,)+args,kw)
        self.im=im
        menu=Menu(self)
        self.config(menu=menu)
        myim=Menu(menu)
        menu.add_cascade(label="My IM",menu=myim)
        #statuschange=Menu(myim)
        #myim.add_cascade(label="Change Status",menu=statuschange)
        #for k in service.statuses.keys():
        #    statuschange.add_command(label=service.statuses[k],command=lambda im=self.im,status=k:im.remote.changeStatus(status))
        myim.add_command(label="Account Manager",command=lambda i=self.im:AccountManager(i))
        self.list=Listbox(self,height=2)
        self.list.grid(column=0,row=0,sticky=N+E+S+W)
        bar=Scrollbar(self)
        bar.grid(column=4,row=0,sticky=N+S)
        self.list.config(yscrollcommand=bar.set)
        bar.config(command=self.list.yview)
        f=Frame(self)
        Button(f,text="Add Contact",command=self.addContact).grid(column=0,row=1)
        Button(f,text="Remove Contact",command=self.removeContact).grid(column=1,row=1)
        Button(f,text="Send Message",command=self.sendMessage).grid(column=2,row=1)
        Button(f,text="Join Group",command=self.joinGroup).grid(column=3,row=1)
        f.grid(column=0,row=1,columnspan=2)
        self.title("Instance Messenger")
        self.protocol("WM_DELETE_WINDOW",self.close)
        self.columnconfigure(0,weight=1)
        self.rowconfigure(0,weight=1)
    
    def close(self):
        self.tk.quit()
        self.destroy()

    def addContact(self):
        AddContact(self.im)
    
    def removeContact(self):
        gatewayname,contact,state=string.split(self.list.get(ACTIVE)," : ")
        self.list.delete(ACTIVE)
        self.im.removeContact(gatewayname,contact)
    
    def changeContactStatus(self,gatewayname,contact,status):
        users=list(self.list.get(0,END))
        start="%s : %s" % (gatewayname,contact)
        for u in users:
            if u[:len(start)]==start:
                row=users.index(u)
                self.list.delete(row)
        self.list.insert(END,"%s : %s : %s"%(gatewayname,contact,status))
    
    def sendMessage(self):
        gatewayname,user,state=string.split(self.list.get(ACTIVE)," : ")
        self.im.conversationWith(gatewayname,user)
    
    def joinGroup(self):
        JoinGroup(self.im)
        
class ChooseGateway(Toplevel):
    def __init__(self,callback,**kw):
        apply(Toplevel.__init__,(self,),kw)
        self.callback=callback
        self.title("Choose a Gateway - Instance Messenger")
        self.gateways=[]
        self.list=Listbox(self)
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

class AddGateway(Toplevel):
    def __init__(self,gateway,acctman,**kw):
        apply(Toplevel.__init__,(self,),kw)
        self.gateway=gateway
        self.acctman=acctman
        self.title("Add %s Gateway - Instance Messenger"%gateways.__gateways__[gateway].shortName)
        self.options={}
        useroptions=gateways.__gateways__[gateway].loginOptions
        r=0
        for title,key,default in useroptions:
            dict={}
            if len(key)>3 and key[:4]=="pass":
                dict["show"]="*"
            Label(self,text=title).grid(column=0,row=r,sticky=W+N)
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
        Button(self,text="OK",command=self.addGateway).grid(column=0,row=r,sticky=N+W)
        Button(self,text="Cancel",command=self.destroy).grid(column=1,row=r,sticky=E+W)
        self.protocol("WM_DELETE_WINDOW",self.destroy)

    def addGateway(self):
        o={}
        for k in self.options.keys():
            o[k]=self.options[k].get()
        auto=self.autologon.get()
        savepass=self.savepass.get()
        self.acctman._addgateway(self.gateway,o,auto,savepass)
        self.destroy()

class AccountManager(Toplevel):
    def __init__(self,im,*args,**kw):
        apply(Toplevel.__init__,(self,)+args,kw)
        self.title("Account Manager - Instance Messenger")
        self.im=im
        self.gateways={}
        sb=Scrollbar(self)
        self.list=tkutil.CList(self,["Username    ","Online","Auto-Logon","Gateway    "],yscrollcommand=sb.set)
        sb.config(command=self.list.yview)
        self.list.grid(column=0,row=0,columnspan=4,sticky=N+E+S+W)
        sb.grid(column=4,row=0,sticky=N+S)
        Button(self,text="Add",command=self.addGateway).grid(column=0,row=1,sticky=E+S+W)
        Button(self,text="Modify",command=self.modifyGateway).grid(column=1,row=1,sticky=E+S+W)
        Button(self,text="Log On/Off",command=self.logOnOff).grid(column=2,row=1,sticky=E+S+W)
        Button(self,text="Delete",command=self.deleteGateway).grid(column=3,row=1,sticky=E+S+W)
        tkutil.grid_setexpand(self)
        self.protocol("WM_DELETE_WINDOW",self.close)

    def close(self):
        self.destroy()
        if self.im.cl==None: self.tk.quit() 
    def addGateway(self):
        ChooseGateway(callback=lambda g,s=self:AddGateway(g,s))
        
    def _addgateway(self,gateway,options,autologon,savepass):
        sn=gateways.__gateways__[gateway].shortName
        name=sn+" "+options["username"] # assumes username is an option
        self.gateways[name]=options,autologon,savepass
        auto=autologon and "True" or "False"
        self.list.insert(END,(options["username"],"Not Being Used",auto,sn))
        
    def modifyGateway(self):
        print "modify doesn't work yet" 
        
    def logOnOff(self):
        index=self.list.index(ACTIVE)
        username,online,auto,gateway=self.list.get(index)
        name=gateway+" "+username
        options=self.gateways[name]
        for k in gateways.__gateways__.keys():
            if gateways.__gateways__[k].shortName==gateway:
                gateway=k
                break
        apply(gateways.__gateways__[gateway].makeConnection,(self.im,),options[0])
    def deleteGateway(self):
        index=self.list.index(ACTIVE)
        l=self.list.get(index)
        if not l: return
        username,online,auto,gateway=l
        name=gateway+" "+username
        #del self.
        print "doesn't work yet"

im2.Conversation=Conversation
im2.ContactList=ContactList
im2.GroupSession=GroupSession
im2.ErrorWindow=lambda gn,code,error,message:ErrorWindow(code,message)

def main():
    global im
    root=Tk()
    root.withdraw()
    tkinternet.install(root)
    root.withdraw()
    im=im2.InstanceMessenger()
    #im.logging=1
    #o=[]
    #for label,key,default in words.loginOptions:
    #    if key[:4]=="pass": # probably a password
    #        o.append([label,default,{"show":"*"}])
    #    else:
    #        o.append([label,default])
    #lw=tkutil.GenericLogin(lambda kw,f=words.makeConnection,o=words.loginOptions,a=(im,):fix_apply_values(f,o,a,kw),o)
    AccountManager(im)
    mainloop()
    tkinternet.stop()

if __name__=="__main__":main()
