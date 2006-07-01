# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""TOC (i.e. AIM) support for Instance Messenger."""

# System Imports
import string, re
from zope.interface import implements

# Twisted Imports
from twisted.words.protocols import toc
from twisted.words.im.locals import ONLINE, OFFLINE, AWAY
from twisted.internet import defer, reactor, protocol
from twisted.internet.defer import succeed

# Sibling Imports
from twisted.words.im import basesupport, interfaces, locals

def dehtml(text):
    text=string.replace(text,"<br>","\n")
    text=string.replace(text,"<BR>","\n")
    text=string.replace(text,"<Br>","\n") # XXX make this a regexp
    text=string.replace(text,"<bR>","\n")
    text=re.sub('<.*?>','',text)
    text=string.replace(text,'&gt;','>')
    text=string.replace(text,'&lt;','<')
    text=string.replace(text,'&amp;','&')
    text=string.replace(text,'&nbsp;',' ')
    text=string.replace(text,'&#34;','"')
    return text

def html(text):
    text=string.replace(text,'"','&#34;')
    text=string.replace(text,'&amp;','&')
    text=string.replace(text,'&lt;','<')
    text=string.replace(text,'&gt;','>')
    text=string.replace(text,"\n","<br>")
    return '<font color="#000000" back="#ffffff" size=3>%s</font>'%text

class TOCPerson(basesupport.AbstractPerson):
    def isOnline(self):
        return self.status != OFFLINE

    def getStatus(self):
        return self.status

    def getIdleTime(self):
        return str(self.idletime)

    def setStatusAndIdle(self, status, idletime):
        if self.account.client is None:
            raise locals.OfflineError
        self.status = status
        self.idletime = idletime
        self.account.client.chat.getContactsList().setContactStatus(self)

    def sendMessage(self, text, meta=None):
        if self.account.client is None:
            raise locals.OfflineError
        if meta:
            if meta.get("style", None) == "emote":
                text="* "+text+"* "
        self.account.client.say(self.name,html(text))
        return succeed(text)

class TOCGroup(basesupport.AbstractGroup):
    implements(interfaces.IGroup)
    def __init__(self, name, tocAccount):
        basesupport.AbstractGroup.__init__(self, name, tocAccount)
        self.roomID = self.client.roomID[self.name]

    def sendGroupMessage(self, text, meta=None):
        if self.account.client is None:
            raise locals.OfflineError
        if meta:
            if meta.get("style", None) == "emote":
                text="* "+text+"* "
        self.account.client.chat_say(self.roomID,html(text))
        return succeed(text)

    def leave(self):
        if self.account.client is None:
            raise locals.OfflineError
        self.account.client.chat_leave(self.roomID)


class TOCProto(basesupport.AbstractClientMixin, toc.TOCClient):
    def __init__(self, account, chatui, logonDeferred):
        toc.TOCClient.__init__(self, account.username, account.password)
        basesupport.AbstractClientMixin.__init__(self, account, chatui,
                                                 logonDeferred)
        self.roomID = {}
        self.roomIDreverse = {}

    def _debug(self, m):
        pass #print '<toc debug>', repr(m)

    def getGroupConversation(self, name, hide=0):
        return self.chat.getGroupConversation(
            self.chat.getGroup(name, self), hide)

    def addContact(self, name):
        self.add_buddy([name])
        if not self._buddylist.has_key('TwistedIM'):
            self._buddylist['TwistedIM'] = []
        if name in self._buddylist['TwistedIM']:
            # whoops, don't add again
            return
        self._buddylist['TwistedIM'].append(name)
        self.set_config(self._config_mode, self._buddylist, self._permit, self._deny)

    def getPerson(self,name):
        return self.chat.getPerson(name, self)

    def onLine(self):
        self.account._isOnline = 1
        #print '$$!&*$&!(@$*& TOC ONLINE *!#@&$(!*%&'

    def gotConfig(self, mode, buddylist, permit, deny):
        #print 'got toc config', repr(mode), repr(buddylist), repr(permit), repr(deny)
        self._config_mode = mode
        self._buddylist = buddylist
        self._permit = permit
        self._deny = deny
        if permit:
            self._debug('adding permit')
            self.add_permit(permit)
        if deny:
            self._debug('adding deny')
            self.add_deny(deny)
        clist=[]
        for k in buddylist.keys():
            self.add_buddy(buddylist[k])
            for name in buddylist[k]:
                self.getPerson(name).setStatusAndIdle(OFFLINE, '--')
        self.signon()
    name = None
    def tocNICK(self,data):
        if not self.name:
            print 'Waiting for second NICK', data
            self.name=data[0]
            self.accountName = '%s (TOC)' % self.name
            self.chat.getContactsList()
        else:
            print 'reregistering...?', data
            self.name=data[0]
            # self.accountName = "%s (TOC)"%data[0]
            if self._logonDeferred is not None:
                self._logonDeferred.callback(self)
                self._logonDeferred = None

    ### Error Messages
    def hearError(self, code, args):
        print '*** TOC ERROR ***', repr(code), repr(args)
    def hearWarning(self, newamount, username):
        print '*** TOC WARNING ***', repr(newamount), repr(username)
    ### Buddy Messages
    def hearMessage(self,username,message,autoreply):
        if autoreply:
            message='<AUTO-REPLY>: '+message
        self.chat.getConversation(self.getPerson(username)
                             ).showMessage(dehtml(message))
    def updateBuddy(self,username,online,evilness,signontime,idletime,userclass,away):
        if away:
            status=AWAY
        elif online:
            status=ONLINE
        else:
            status=OFFLINE
        self.getPerson(username).setStatusAndIdle(status, idletime)

    ### Group Chat
    def chatJoined(self, roomid, roomname, users):
        self.roomID[roomname]=roomid
        self.roomIDreverse[roomid]=roomname
        self.getGroupConversation(roomname).setGroupMembers(users)
    def chatUpdate(self,roomid,member,inroom):
        group=self.roomIDreverse[roomid]
        if inroom:
            self.getGroupConversation(group).memberJoined(member)
        else:
            self.getGroupConversation(group).memberLeft(member)
    def chatHearMessage(self, roomid, username, message):
        if toc.normalize(username) == toc.normalize(self.name):
            return # ignore the message
        group=self.roomIDreverse[roomid]
        self.getGroupConversation(group).showGroupMessage(username, dehtml(message))
    def chatHearWhisper(self, roomid, username, message):
        print '*** user whispered *** ', roomid, username, message
    def chatInvited(self, roomid, roomname, username, message):
        print '*** user invited us to chat *** ',roomid, roomname, username, message
    def chatLeft(self, roomid):
        group=self.roomIDreverse[roomid]
        self.getGroupConversation(group,1)
        del self.roomID[group]
        del self.roomIDreverse[roomid]
    def rvousProposal(self,type,cookie,user,vip,port,**kw):
        print '*** rendezvous. ***', type, cookie, user, vip, port, kw
    def receiveBytes(self, user, file, chunk, sofar, total):
        print '*** File transfer! ***', user, file, chunk, sofar, total

    def joinGroup(self,name):
        self.chat_join(4,toc.normalize(name))

class TOCAccount(basesupport.AbstractAccount):
    implements(interfaces.IAccount)
    gatewayType = "AIM (TOC)"

    _groupFactory = TOCGroup
    _personFactory = TOCPerson

    def _startLogOn(self, chatui):
        logonDeferred = defer.Deferred()
        cc = protocol.ClientCreator(reactor, TOCProto, self, chatui,
                                    logonDeferred)
        d = cc.connectTCP(self.host, self.port)
        d.addErrback(logonDeferred.errback)
        return logonDeferred

