
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
from twisted.spread.ui import tkutil
from twisted.internet import tkinternet
from twisted.words.ui import im2
from twisted.words.ui import gateways
import time
import string
import cPickle
import copy
import os

class ErrorWindow(Toplevel):
    def __init__(self,error,message,*args,**kw):
        apply(Toplevel.__init__,(self,)+args,kw)
        self.title(error)
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
            self.im.addContact(self.im.gateways[gatewayname],contact)
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

class GroupSession(Toplevel):
    def __init__(self,im,name,gateway,*args,**kw):
        apply(Toplevel.__init__,(self,)+args,kw)
        self.title("%s - Instance Messenger"%name)
        self.name=name
        self.im=im
        self.gateway=gateway
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
        self.im.getGroupMembers(gateway,self.name)

    def close(self):
        self.im.leaveGroup(self.gateway,self.name)
        self.destroy()
    
    def _out(self,text):
        self.output.config(state=NORMAL)
        #self.outputhtml.feed(text)
        self.output.insert(END,text)
        self.output.see(END)
        self.output.config(state=DISABLED)
    
    def receiveGroupMembers(self,list):
        for m in list:
            self.list.insert(END,m)
    
    def displayMessage(self,user,message):
        self._out("<%s> %s\n"%(user,message))
    
    def memberJoined(self,user):
        self._out("%s joined!\n"%user)
        self.list.insert(END,user)
    
    def memberLeft(self,user):
        self._out("%s left!\n"%user)
        users=list(self.list.get(0,END))
        i=users.index(user)
        self.list.delete(i)
    
    def say(self,*args):
        text=self.input.get("1.0",END)[:-1]
        if not text: return
        self.input.delete("1.0",END)
        self.im.groupMessage(self.gateway,self.name,text)
        self._out("<<%s>> %s\n"%(self.gateway.username,text))
        return "break"
        
class Conversation(Toplevel):
    def __init__(self,im,gateway,contact,*args,**kw):
        apply(Toplevel.__init__,(self,)+args,kw)
        self.contact=contact
        self.im=im
        self.gateway=gateway
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
        self.destroy()
        self.im.endConversation(self.gateway,self.contact)
    
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
            self.messageReceived(message,self.gateway.username)
            self.im.directMessage(self.gateway,self.contact,message)
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
        myim.add_command(label="Account Manager",command=lambda i=self.im:i.am.deiconify())
        bar=Scrollbar(self)
        self.list=tkutil.CList(self,["Gateway","Username","Status"],height=2,yscrollcommand=bar.set)
        self.list.grid(column=0,row=0,sticky=N+E+S+W)
        bar.grid(column=4,row=0,sticky=N+S)
        bar.config(command=self.list.yview)
        f=Frame(self)
        Button(f,text="Add Contact",command=self.addContact).grid(column=0,row=1)
        Button(f,text="Remove Contact",command=self.removeContact).grid(column=1,row=1)
        Button(f,text="Send Message",command=self.sendMessage).grid(column=2,row=1)
        Button(f,text="Join Group",command=self.joinGroup).grid(column=3,row=1)
        f.grid(column=0,row=1,columnspan=2,sticky=E+S+W)
        self.title("Instance Messenger")
        self.protocol("WM_DELETE_WINDOW",self.close)
        tkutil.grid_setexpand(self)
        #self.columnconfigure(0,weight=1)
        self.rowconfigure(1,weight=0)
    
    def close(self):
        self.tk.quit()
        self.destroy()

    def addContact(self):
        AddContact(self.im)
    
    def removeContact(self):
        gatewayname,contact,state=self.list.get(ACTIVE)
        self.list.delete(ACTIVE)
        self.im.removeContact(gatewayname,contact)

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
    
    def sendMessage(self):
        gatewayname,user,state=self.list.get(ACTIVE)
        self.im.conversationWith(self.im.gateways[gatewayname],user)
    
    def joinGroup(self):
        JoinGroup(self.im)
        
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

class AddGateway(Toplevel):
    def __init__(self,gateway,acctman,**kw):
        apply(Toplevel.__init__,(self,),kw)
        self.gateway=gateway
        self.acctman=acctman
        self.title("Add %s Gateway - Instance Messenger"%gateway)
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

class ModifyGateway(Toplevel):
    def __init__(self,acctman,gateway,options,autologon,savepass,**kw):
        apply(Toplevel.__init__,(self,),kw)
        self.gateway=gateway
        self.acctman=acctman
        self.username=options["username"]
        self.title("Modify %s Gateway - Instance Messenger"%gateway)
        self.options={}
        useroptions=gateways.__gateways__[gateway].loginOptions
        r=0
        for title,key,default in useroptions:
            dict={}
            if len(key)>3 and key[:4]=="pass":
                dict["show"]="*"
            Label(self,text=title+": ").grid(column=0,row=r,sticky=W+N)
            if key!="username":
                entry=apply(Entry,(self,),dict)
                entry.insert(0,options[key])
                entry.grid(column=1,row=r,sticky=E+N)
                self.options[key]=entry
            else:
                Label(self,text=options[key],relief=SUNKEN,anchor=W).grid(column=1,row=r,sticky=W+E+N)
            r=r+1
        self.autologon=IntVar()
        self.autologon.set(autologon)
        Checkbutton(self,text="Auto Logon?",variable=self.autologon).grid(column=0,row=r,columnspan=2,sticky=W+E+N)
        r=r+1
        self.savepass=IntVar()
        self.savepass.set(savepass)
        Checkbutton(self,text="Save Password?",variable=self.savepass).grid(column=0,row=r,columnspan=2,sticky=W+E+N)
        r=r+1
        Button(self,text="OK",command=self.modifyGateway).grid(column=0,row=r,sticky=N+W)
        Button(self,text="Cancel",command=self.destroy).grid(column=1,row=r,sticky=E+W)
        self.protocol("WM_DELETE_WINDOW",self.destroy)

    def modifyGateway(self):
        o={}
        for k in self.options.keys():
            o[k]=self.options[k].get()
        o["username"]=self.username
        auto=self.autologon.get()
        savepass=self.savepass.get()
        self.acctman._modifygateway(self.gateway,o,auto,savepass)
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
        self.list.grid(column=0,row=0,sticky=N+E+S+W)
        sb.grid(column=1,row=0,sticky=N+S+E)
        f=Frame(self)
        Button(f,text="Add",command=self.addGateway).grid(column=0,row=0,sticky=N+E+S+W)
        Button(f,text="Modify",command=self.modifyGateway).grid(column=1,row=0,sticky=N+E+S+W)
        Button(f,text="Log On/Off",command=self.logOnOff).grid(column=2,row=0,sticky=N+E+S+W)
        Button(f,text="Delete",command=self.deleteGateway).grid(column=3,row=0,sticky=N+E+S+W)
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
    
    def saveState(self,file):
        options=copy.copy(self.gateways)
        for o in options.values():
            if not o[2]: # don't save password
                for k in o[0].keys():
                    if k[:4]=="pass":
                        del o[0][k]
        cPickle.dump(options.values(),file)

    def loadState(self,file):
        options=cPickle.load(file)
        autos=[]
        for o in options:
            self._addgateway(o[3],o[0],o[1],o[2])
            if o[1]: # autologon
                autos.append(o)
        for o in autos:
            self.logonGateway(o)

    def addGateway(self):
        ChooseGateway(callback=lambda g,s=self:AddGateway(g,s))
        
    def _addgateway(self,gatewayname,options,autologon,savepass,online=0):
        name=gatewayname+" "+options["username"] # assumes username is an option
        self.gateways[name]=options,autologon,savepass,gatewayname
        auto=autologon and "True" or "False"
        online=online and "True" or "False"
        self.list.insert(END,(options["username"],online,auto,gatewayname))
        
    def modifyGateway(self):
        index=self.list.index(ACTIVE)
        username,online,auto,gateway=self.list.get(index)
        try:
            options=self.gateways[gateway+" "+username]
        except:
            return
        ModifyGateway(self,gateway,options[0],options[1],options[2])
        
    def _modifygateway(self,gatewayname,options,autologon,savepass,online="False"):
        name=gatewayname+" "+options["username"] # assumes username is an option
        self.gateways[name]=options,autologon,savepass,gatewayname
        auto=autologon and "True" or "False"
        gate=self.list.get(0,END)
        for i in range(len(gate)):
            username,foo,bar,gn=gate[i]
            if gn+" "+username==name:
                self.list.delete(i)
                self.list.insert(i,[username,online,auto,gn])

    def logOnOff(self):
        index=self.list.index(ACTIVE)
        username,online,auto,gateway=self.list.get(index)
        name=gateway+" "+username
        try:
            options=self.gateways[name]
        except:
            return
        if online=="False":
            self.logonGateway(options)
        else:
            for g in self.im.gateways.values():
                if g.username==username and g.protocol==gateway:
                    self.im.addCallback(g,"error", \
                        self.handleDisconnectGracefully)
                    g.transport.loseConnection()
    
    def logonGateway(self,options):
        gateway=options[3]
        username=options[0]["username"]
        self._modifygateway(gateway,options[0],options[1],options[2],"Attempting")      
        if len(options[0])<len(gateways.__gateways__[gateway].loginOptions):
            for foo,key,bar in gateways.__gateways__[gateway].loginOptions:
                if not options[0].has_key(key):
                    if key[:4]=="pass":
                        value=tkutil.askpassword("Enter %s for %s"%(foo,username),foo+": ")
                    else:
                        value=tkSimpleDialog.askstring("Enter "+foo,foo+": ")
                    self.gateways[gateway+" "+username][0][key]=value
        apply(gateways.__gateways__[gateway].makeConnection,(self.im,),options[0])
    
    def deleteGateway(self):
        index=self.list.index(ACTIVE)
        username,online,auto,gateway=self.list.get(index)
        self.list.delete(index)
        for g in self.im.gateways.values():
            if g.protocol==gateway and g.username==username:
                self.im.addCallback(g,"error", \
                    self.handleDisconnectGracefully)
                g.transport.loseConnection()
        try:
            del self.gateways[gateway+" "+username]
        except:
            pass

    def handleAttached(self,im,gateway,event):
        name=gateway.protocol+" "+gateway.username
        options=self.gateways[name]
        self._modifygateway(gateway.protocol,options[0],options[1],options[2],"True")

    def handleDetached(self,im,gateway,event):
        if im.cl!=None: im.cl.removeGateway(gateway)
        try:
            options=self.gateways[gatway.protocol+" "+gateway.username]
        except:
            return
        self._modifygateway(gateway.protocol,options[0],options[1],options[2],"False")

    def handleDisconnectGracefully(self,im,gateway,event,code,message):
        im.removeCallback(gateway,event,self.handleDisconnectGracefully)
        if code==im2.CONNECTIONLOST: return "break"

im2.Conversation=Conversation
im2.ContactList=ContactList
im2.GroupSession=GroupSession
im2.ErrorWindow=ErrorWindow

def main():
    global im
    root=Tk()
    root.withdraw()
    tkinternet.install(root)
    root.withdraw()
    im=im2.InstanceMessenger()
    im.am=AccountManager(im)
    try:
        f=open(os.path.expanduser("~/.imsaved"),"r")
    except:
        pass
    else:
        im.am.loadState(f)
    mainloop()
    tkinternet.stop()
    f=open(os.path.expanduser("~/.imsaved"),"w")
    im.am.saveState(f)

if __name__=="__main__":main()
