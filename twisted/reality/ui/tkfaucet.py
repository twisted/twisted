import string
import copy

from Tkinter import *
from ScrolledText import *

from twisted.spread import pb
from twisted.internet import tkinternet, main, tcp

portno = 8787

##class TKFaucet(gloop.ClientThread):
##    def __init__(self, host, port, char, paswd, window):
##        self.window = window
##        gloop.ClientThread.__init__(self, host, port, char, paswd)
        
##    def connectionLost(self):
##        self.window.close()

##    def localSetup(self):
##        'making sure "client" is available to server'
##        self.addName('client', self.window)
        
##    def remoteSetup(self):
##        'setting up "execute" from server'
##        self.window.sendVerb_ = self['execute']


class MainWindow(Toplevel, pb.Referenced):
    def __init__(self, *args,**kw):
        self.descriptions = {}
        self.items = {}
        self.exits = []
        apply(Toplevel.__init__,(self,)+args,kw)
        self.title("Reality Faucet")
        self.happenings = ScrolledText(self, height=5, width=5)
        
        midf = Frame(self)
        ddf = Frame(midf)
        idf = Frame(midf)
        
        a = self.descriptionField = ScrolledText(ddf, height=5, width=5)
        b = self.itemsField = ScrolledText(idf, height=5, width=30)
        a.pack(fill=BOTH, expand=YES)
        b.pack(fill=BOTH, expand=YES)
        ddf.pack(side=LEFT, fill=BOTH, expand=YES)
        idf.pack(side=LEFT, fill=BOTH, expand=NO)
        
        f=Frame(self)
        self.entry=Entry(f)
        self.bind("<Return>",self.doSend)
        # self.bind("<KP-1>", self.doSend)
        self.button=Button(f,text=".",command=self.doSend)
        self.entry.pack(side=LEFT,expand=YES,fill=BOTH)
        self.button.pack(side=LEFT)

        self.nameLabel = Label(self, text="hellO")
        
        f.pack(side=BOTTOM, expand=NO, fill='x')
        self.happenings.pack(side=BOTTOM, expand=YES, fill=BOTH)
        midf.pack(side=BOTTOM, expand=YES, fill=BOTH)
        self.nameLabel.pack(side=TOP, expand=NO)
        
        self.protocol("WM_DELETE_WINDOW",self.close)

    def close(self):
        self.tk.quit()
        self.destroy()

    def verbSuccess(self, nne):
        self.verbDone()

    def verbFailure(self, nne):
        if hasattr(nne, 'traceback'):
            self.seeEvent(nne.traceback)
        self.seeEvent(nne)
        self.verbDone()

    def verbDone(self):
        # unlock the text field
        pass 

    def doNow(self, verb):
        self.remote.execute(verb,
                            pbcallback = self.verbSuccess,
                            pberrback = self.verbFailure)

    def remote_seeEvent(self,text):
        self.happenings.insert('end',text+'\n')
        self.happenings.see('end')

    def reitem(self):
        self.itemsField.delete('1.0','end')
        self.itemsField.insert('end', string.join(self.items.values(), '\n'))

    def redesc(self):
        z = copy.copy(self.descriptions)
        m = z.get('__MAIN__','')
        e = z.get('__EXITS__','')

        try: del z['__MAIN__']
        except: pass
        try: del z['__EXITS__']
        except: pass
        
        self.descriptionField.delete(1.0,'end')
        self.descriptionField.insert('end', string.join([m]+z.values()+[e]))

    def remote_seeName(self, name):
        self.nameLabel.configure(text=name)

    def remote_dontSeeItem(self, key,parent):
        try:
            del self.items[key]
        except:
            print 'tried to remove nonexistant item %s' % str(key)
        self.reitem()
    
    def doSend(self, *evstuf):
        sentence = self.entry.get()
        self.doNow(sentence)
        self.entry.delete('0','end')

    def remote_dontSeeItem(self,key,parent):
        try: del self.items[key]
        except: print 'tried to remove nonexistant item %s' % str(key)
        self.reitem()
        
    def remote_seeNoItems(self):
        self.items = {}
        self.reitem()
    
    def remote_seeItem(self,key,parent,value):
        self.items[key] = value
        self.reitem()
        
    def remote_seeDescription(self,key,value):
        self.descriptions[key] = value
        self.redesc()

    def remote_dontSeeDescription(self,key):
        del self.descriptions[key]
        self.redesc()

    def remote_seeNoDescriptions(self):
        self.descriptions = {}
        self.redesc()

    def reexit(self):
        self.remote_seeDescription('__EXITS__',"\nObvious Exits: %s"%string.join(self.exits,', '))
        
    def remote_seeExit(self,exit):
        self.exits.append(exit)
        self.reexit()

    def remote_dontSeeExit(self,exit):
        self.exits.remove(exit)
        self.reexit()

    def remote_seeNoExits(self):
        self.exits = []
        self.reexit()


class Login(Toplevel):
    def __init__(self, *args,**kw):
        apply(Toplevel.__init__,(self,)+args,kw)
        f = Frame(self)
        l = Label(f,text='Username:')
        self.username = Entry(f)
        self.username.insert('0','Damien')

        l.grid(column=0,row=0); self.username.grid(column=1,row=0)

        l=Label(f,text="Password: ")
        self.password=Entry(f,show="*")
        self.password.insert('0','admin')

        l.grid(column=0,row=1); self.password.grid(column=1,row=1)

        l=Label(f,text="World: ")
        self.worldname=Entry(f)
        self.worldname.insert('0','reality')

        l.grid(column=0,row=2); self.worldname.grid(column=1,row=2)

        l=Label(f,text="Hostname: ")
        self.hostname=Entry(f)
        self.hostname.insert('0','localhost')

        l.grid(column=0,row=3); self.hostname.grid(column=1,row=3)

        l=Label(f,text="Port:")
        self.port=Entry(f)
        self.port.insert('0',str(portno))

        l.grid(column=0,row=4); self.port.grid(column=1,row=4)
        f.pack()

        self.go=Button(self,text="Login",command=self.doLogin)
        self.go.pack()
        self.resizable(width=0,height=0)
        self.bind('<Return>',self.doLogin)
        self.protocol("WM_DELETE_WINDOW",self.close)

    def close(self):
        self.tk.quit()
        self.destroy()

    def doLogin(self, *ev):
        username=self.username.get()
        hostname=self.hostname.get()
        worldname=self.worldname.get()
        try:
            port=int(self.port.get())
        except:
            port = self.port.get()
        password=self.password.get()
        broker = pb.Broker()
        broker.requestPerspective(worldname, username, password, self.loggedIn, self.tryAgain)
        broker.notifyOnDisconnect(self.disco)
        tcp.Client(hostname, port, broker)

    def loggedIn(self, perspective):
        m = MainWindow()
        m.remote = perspective
        perspective.observe(m)
        self.withdraw()

    def tryAgain(self):
        print 'try again'

    def disco(self):
        print 'disconnected'

def main():
    global root
    root = Tk()
    root.withdraw()
    tkinternet.install(root)
    print 'displaying login'
    Login(root)
    mainloop()
    tkinternet.stop()
