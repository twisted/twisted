from Tkinter import *
import tkSimpleDialog
from twisted.spread import pb
from twisted.spread.ui import tkutil
from twisted.internet import tkinternet
from twisted.words import service
from twisted.words.ui import im
import time
import string

class Group(pb.Cache):
    """A local cache of a group.
    """
pb.setCopierForClass("twisted.words.service.Group",Group)

class ErrorWindow(Toplevel):
    def __init__(self,code,message,*args,**kw):
        apply(Toplevel.__init__,(self,)+args,kw)
        self.title("Error %s"%code)
        f=Frame(self)
        Label(f,text=message).grid()
        f.pack()
        self.protocol("WM_DELETE_WINDOW",self.destroy)
class GroupSession(Toplevel):
    def __init__(self,name,im,*args,**kw):
        apply(Toplevel.__init__,(self,)+args,kw)
        self.title("%s - Instance Messenger"%name)
        self.name=name
        self.im=im
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
        self._nolist=0
        self.im.remote.getGroupMembers(self.name,pbcallback=self.gotGroupMembers,pberrback=self.noGroupMembers)
    def close(self):
        self.im.remote.leaveGroup(self.name)
        self.destroy()
    def _out(self,text):
        self.output.config(state=NORMAL)
        #self.outputhtml.feed(text)
        self.output.insert(END,text)
        self.output.see(END)
        self.output.config(state=DISABLED)
    def gotGroupMembers(self,list):
        for m in list:
            self.list.insert(END,m)
    def noGroupMembers(self,tb):
        self._nolist=1
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
        self.im.remote.groupMessage(self.name,text)
        self._out("<<%s>> %s\n"%(self.im.name,text))
        return "break"
class MessageSent:
    def __init__(self,im,conv,mesg):
        self.im=im
        self.conv=conv
        self.mesg=mesg
    def success(self,result):
        self.conv.messageReceived(self.mesg,self.im.name)
    def failure(self,tb):
        self.conv.messageReceived("could not send message %s: %s"%(repr(self.mesg),tb),"error")
class Conversation(Toplevel):
    def __init__(self,im,contact,*args,**kw):
        apply(Toplevel.__init__,(self,)+args,kw)
        self.contact=contact
        self.im=im
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
        del self.im.conversations[self.contact]
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
            ms=MessageSent(self.im,self,message)
            self.im.remote.directMessage(self.contact,message,
                                                    pbcallback=ms.success,
                                                    pberrback=ms.failure)
        return "break" # don't put the newline in
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
        for k in service.statuses.keys():
            statuschange.add_command(label=service.statuses[k],command=lambda im=self.im,status=k:im.remote.changeStatus(status))
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
        contact=tkSimpleDialog.askstring("Add Contact","What user do you want to add to your contact list?")
        if contact:self.im.remote.addContact(contact)
    def removeContact(self):
        contact=string.split(self.list.get(ACTIVE)," :")[0]
        self.list.delete(ACTIVE)
        self.im.remote.removeContact(contact)
    def changeContactStatus(self,contact,status):
        users=list(self.list.get(0,END))
        for u in users:
            if u[:len(contact)]==contact:
                row=users.index(u)
                self.list.delete(row)
        self.list.insert(END,"%s : %s"%(contact,service.statuses[status]))
    def sendMessage(self):
        user=string.split(self.list.get(ACTIVE)," : ")[0]
        self.im.conversationWith(user)
    def joinGroup(self):
        name=tkSimpleDialog.askstring("Join Group","What group do you want to join?")
        if name:
            self.im.remote.joinGroup(name)
            self.im.groups[name]=GroupSession(name,self.im)

im.Conversation=Conversation
im.ContactList=ContactList
def our_connected(perspective):
    b.name=lw.username.get()
    b.connected(perspective)
    lw.destroy()
def main():
    global lw,b
    root=Tk()
    root.withdraw()
    tkinternet.install(root)
    b=im.InstanceMessenger()
    lw=tkutil.Login(our_connected,b,initialPassword="guest",initialService="twisted.words")
    mainloop()
    tkinternet.stop()

if __name__=="__main__":main()
