from Tkinter import *

from twisted.spread import pb
from twisted.internet import tcp
from twisted import copyright


#normalFont = Font("-adobe-courier-medium-r-normal-*-*-120-*-*-m-*-iso8859-1")
#boldFont = Font("-adobe-courier-bold-r-normal-*-*-120-*-*-m-*-iso8859-1")
#errorFont = Font("-adobe-courier-medium-o-normal-*-*-120-*-*-m-*-iso8859-1")

def grid_setexpand(widget):
    cols,rows=widget.grid_size()
    for i in range(cols):
        widget.columnconfigure(i,weight=1)
    for i in range(rows):
        widget.rowconfigure(i,weight=1)
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
        self.pbReferenced = referenced
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
        identity.attach(self.service.get(),self.pbReferenced,pbcallback=self.pbCallback)

    def couldNotConnect(self,*args):
        self.loginReport("could not connect.")

    def disconnected(self,*args):
        self.loginReport("disconnected from server.")
