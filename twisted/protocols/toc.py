"""
Implements a AOL Instant Messenger TOC server and client, using the Twisted framework.
"""

import protocol
import struct
import string
import time
SIGNON,DATA,ERROR,SIGNOFF,KEEP_ALIVE=range(1,6)
DENYALL,DENYSOME,PERMITALL,PERMITSOME=range(1,5)
def quote(s):
    rep=['\\','$','{','}','[',']','(',')','"']
    for r in rep:
        s=string.replace(s,r,"\\"+r)
    return s
def unquote(s):
    if s=="": return ""
    if s[0]!='"': return s
    r=string.replace
    s=s[1:-1]
    s=r(s,"\\\\","\\")
    s=r(s,"\\$","$")
    s=r(s,"\\{","{")
    s=r(s,"\\}","}")
    s=r(s,"\\[","[")
    s=r(s,"\\]","]")
    s=r(s,"\\(","(")
    s=r(s,"\\)",")")
    s=r(s,"\\\"","\"")
    return s
def unquotebeg(s):
    for i in range(1,len(s)):
        if s[i]=='"' and s[i-1]!='\\':
            q=unquote(s[:i+1])
            return [q,s[i+2:]]
def unroast(pw):
    roaststring="Tic/Toc"
    pw=string.lower(pw[2:])
    r=""
    count=0
    hex=["0","1","2","3","4","5","6","7","8","9","a","b","c","d","e","f"]
    while pw:
        st,pw=pw[:2],pw[2:]
        value=(16*hex.index(st[0]))+hex.index(st[1])
        xor=ord(roaststring[count])
        count=(count+1)%len(roaststring)
        r=r+chr(value^xor)
    return r
def roast(pw):
    # contributed by jemfinch on #python
    key="Tic/Toc"
    ro="0x"
    i=0
    ascii=map(ord,pw)
    for c in ascii:
        ro=ro+'%02x'%(c^ord(key[i%len(key)]))
        i=i+1
    return ro
def normalize(s):
    s=string.lower(s)
    s=string.replace(s," ","")
    return s
class TOCParseError(ValueError):
    pass

class TOC(protocol.Protocol):
    users={}
    def connectionMade(self):
        # initialization of protocol
        self._buf=""
        self._ourseqnum=0L
        self._theirseqnum=0L
        self._mode="Flapon"
        self._onlyflaps=0
        self.username=None
        self.permitmode=PERMITALL
        self.permitlist=[]
        self.denylist=[]
        self.buddylist=[]
        self.signontime=0
        self.idletime=0
        self.userclass=" O" 
        self.away=""
        self.saved=None
    def _debug(self,data):
        print data
    def connectionLost(self):
        self._debug("dropped connection from %s" % self.username)
        try:
            del self.factory.users[self.username]
        except:
            pass
        if self.saved:
            self.factory.savedusers[self.username]=self.saved
        self.updateUsers()
    def sendFlap(self,type,data):
        """
        send a FLAP to the client
        """
        send="*"
        self._debug(data)
        if type==DATA:
            data=data+"\000"
        length=len(data) 
        send=send+struct.pack("!BHH",type,self._ourseqnum,length)
        send=send+data
        self._ourseqnum=self._ourseqnum+1
        if self._ourseqnum>(256L**4):
            self._ourseqnum=0
        self.transport.write(send)
    def dataReceived(self,data):
        self._buf=self._buf+data
        try:
            func=getattr(self,"mode%s"%self._mode)
        except:
            return
        self._mode=func()
        if self._onlyflaps and self.isFlap(): self.dataReceived("")
    def isFlap(self):
        """
        tests to see if a flap is actually on the buffer
        """
        if self._buf=='': return 0
        if self._buf[0]!="*": return 0
        if len(self._buf)<6: return 0
        foo,type,seqnum,length=struct.unpack("!BBHH",self._buf[:6])
        if type not in range(1,6): return 0
        if len(self._buf)<6+length: return 0
        return 1
    def readFlap(self):
        """
        read the first FLAP off self._buf, raising errors if it isn't in the right form.
        the FLAP is the basic TOC message format, and is logically equivilant to a packet in TCP
        """
        if self._buf=='': return None
        if self._buf[0]!="*": 
            raise TOCParseError
        if len(self._buf)<6: return None
        foo,type,seqnum,length=struct.unpack("!BBHH",self._buf[:6])
        if len(self._buf)<6+length: return None
        data=self._buf[6:6+length]
        self._buf=self._buf[6+length:]
        if data[-1]=="\000":
            data=data[:-1]
        self._debug([type,data])
        return [type,data]
    def modeFlapon(self):
        if len(self._buf)<10: return "Flapon" # not enough bytes
        flapon,self._buf=self._buf[:10],self._buf[10:]
        if flapon!="FLAPON\r\n\r\n":
            raise TOCParseError
        self.sendFlap(SIGNON,"\000\000\000\001")
        self._onlyflaps=1
        return "Signon"
    def modeSignon(self):
        flap=self.readFlap()
        if flap==None:
            return "Signon"
        if flap[0]!=SIGNON: raise TOCParseError
        version,tlv,unlength=struct.unpack("!LHH",flap[1][:8])
        if version!=1 or tlv!=1 or unlength+8!=len(flap[1]):
            raise TOCParseError
        self.username=normalize(flap[1][8:])
        if self.username in self.factory.savedusers.keys():
            self.saved=self.factory.savedusers[self.username]
        else:
            self.saved=SavedUser()
            self.saved.nick=self.username
        return "TocSignon"
    def modeTocSignon(self):
        flap=self.readFlap()
        if flap==None:
            return "TocSignon"
        if flap[0]!=DATA: raise TOCParseError
        data=string.split(flap[1]," ")
        if data[0]!="toc_signon": raise TOCParseError
        for i in data:
            if not i:data.remove(i)
        password=unroast(data[4])
        if not(self.authorize(data[1],int(data[2]),data[3],password)):
            self.sendError(BAD_NICKNAME)
            self.connectionLost()
            return
        self.sendFlap(DATA,"SIGN_ON:TOC1.0")
        self.sendFlap(DATA,"NICK:%s"%self.saved.nick)
        self.sendFlap(DATA,"CONFIG:%s"%self.saved.config)
        # sending user configuration goes here
        return "Connected"
    
    
    def authorize(self,server,port,username,password):
        #raise NotImplementedError # TODO actually authorize users
        if self.saved.password=="":
            self.saved.password=password
            return 1
        else:
            return self.saved.password==password# use this for testing
    
    
    def modeConnected(self):
        flap=self.readFlap()
        while flap!=None:
            if flap[0] not in [DATA,KEEP_ALIVE]: raise TOCParseError
            flapdata=string.split(flap[1]," ",1)
            tocname=flapdata[0]
            if len(flapdata)==2:
                data=flapdata[1]
            else:
                data=""
            func=getattr(self,tocname,None)
            if func!=None:
                func(data)
            else:
                self.toc_unknown(tocname,data)
            flap=self.readFlap()
        return "Connected"
    def toc_unknown(self,tocname,data):
        self._debug("unknown! %s %s" % (tocname,data))  
    def toc_init_done(self,data):
        """
        called when all the setup is done.

        toc_init_done
        """
        self.signontime=int(time.time())
        self.factory.users[self.username]=self
        self.updateUsers()
    def toc_add_permit(self,data):
        """
        adds users to the permit list.  if the list is null, then set the mode to DENYALL
        """
        if data=="":
            if self.permitmode>=3:
                self.permitmode=DENYALL
                self.permitlist=[]
                self.denylist=[]
        else:
            self.permitmode=PERMITSOME
            self.denylist=[]
            users=string.split(data," ")
            map(self.permitlist.append,users)
        self.updateUsers()
    def toc_add_deny(self,data):
        """
        adds users to the deny list.  if the list is null, then set the mode to PERMITALL
        """
        if data=="":
            if self.permitmode<=2:
                self.permitmode=PERMITALL
                self.permitlist=[]
                self.denylist=[]
        else:
            self.permitmode=DENYSOME
            self.permitlist=[]
            users=string.split(data," ")
            map(self.denylist.append,users)
        self.updateUsers()
    def toc_evil(self,data):
        """
        warns a user.

        toc_evil <username> <anon|norm>
        """
        username,nora=string.split(data," ")
        if nora=="anon":
            user=""
        else:
            user=self.saved.nick
        if not(self.factory.users.has_key(username)):
            self.sendError(CANT_WARN,username)
            return
        if self.factory.users[username].saved.evilness>=100:
            self.sendError(CANT_WARN,username)
            return
        self.factory.users[username].evilFrom(user)
    def toc_add_buddy(self,data):
        """
        adds users to the buddy list
        
        toc_add_buddy <buddyname1> [<buddyname2>] [<buddyname3>]...
        """
        buddies=string.split(data," ")
        map(self.buddylist.append,map(normalize,buddies))
        for buddy in buddies:
            try:
                buddy=self.factory.users[buddy]
            except:
                pass
            else:
                self.buddyUpdate(buddy)
    def toc_remove_buddy(self,data):
        """
        removes users from the buddy list

        toc_remove_buddy <buddyname1> [<buddyname2>] [<buddyname3>]...
        """
        buddies=string.split(data," ")
        map(self.buddylist.remove,map(normalize,buddies))
    def toc_send_im(self,data):
        """
        incoming instant message

        toc_send_im <screenname> <quoted message> [auto]
        """
        username,data=string.split(data," ",1)
        auto=0
        if data[-4:]=="auto":
            auto=1
            data=data[:-5]
        data=unquote(data)
        if not(self.factory.users.has_key(username)):
            self.sendError(NOT_AVAILABLE,username)
            return
        self.factory.users[username].hearWhisper(self,data,auto)
    def toc_set_idle(self,data):
        """
        set/unset idle

        toc_set_idle <seconds>
        """
        seconds=int(data)
        self.idletime=time.time()-seconds # time when they started being idle
        self.updateUsers()
    def toc_set_away(self,data):
        """
        set/unset away message

        toc_set_away [<away message>]
        """
        away=unquote(data)
        if not self.away and away: # setting an away message
            self.away=away
            self.userclass=self.userclass+'U'
            self.updateUsers()
        elif self.away and not away: # coming back
            self.away=""
            self.userclass=self.userclass[:2]
            self.updateUsers()
        else:
            raise TOCParseError
    def toc_chat_join(self,data):
        """
        joins the chat room.

        toc_chat_join <exchange> <room name>
        """
        exchange,name=string.split(data," ",1)
        self.factory.getChatroom(int(exchange),unquote(name)).join(self)
    def toc_chat_invite(self,data):
        """
        invite others to the room.

        toc_chat_invite <room id> <invite message> <buddy 1> [<buddy2>]...
        """
        id,data=string.split(data," ",1)
        id=int(id)
        message,data=unquotebeg(data)
        buddies=string.split(data," ")
        for b in buddies:
            room=self.factory.chatroom[id]
            bud=self.factory.users[b]
            bud.chatInvite(room,self,message)
    def toc_chat_accept(self,data):
        """
        accept an invitation.

        toc_chat_accept <room id>
        """
        id=int(data)
        self.factory.chatroom[id].join(self)
    def toc_chat_send(self,data):
        """
        send a message to the chat room.

        toc_chat_send <room id> <message>
        """
        id,message=string.split(data," ",1)
        id=int(id)
        message=unquote(message)
        self.factory.chatroom[id].say(self,message)
    def toc_chat_leave(self,data):
        """
        leave the room.

        toc_chat_leave <room id>
        """
        id=int(data)
        self.factory.chatroom[id].leave(self)
    def toc_set_config(self,data):
        """
        set the saved config.  this gets send when you log in.

        toc_set_config <config>
        """
        self.saved.config=unquote(data)
    def toc_format_nickname(self,data):
        """
        change the format of your nickname.

        toc_format_nickname <new format>
        """
        # XXX may not work
        nick=unquote(data)
        if normalize(nick)==self.username:
            self.saved.nick=nick
            self.sendFlap(2,"ADMIN_NICK_STATUS:0")
        else:
            self.sendError(BAD_INPUT)
    def toc_change_passwd(self,data):
        orig,data=unquotebeg(data)
        new=unquote(data)
        if orig==self.saved.password:
            self.saved.password=new
            self.sendFlap(2,"ADMIN_PASSWD_STATUS:0")
        else:
            self.sendError(BAD_INPUT)
    def sendError(self,code,*varargs):
        """
        send an error to the user.  listing of error messages is below.
        """
        send="ERROR:%s"%code
        for v in varargs:
            send=send+":"+v
        self.sendFlap(DATA,send)
    def updateUsers(self):
        """
        Update the users who have us on their buddylist.
        Called when the user changes anything (idle,away) so people can get updates.
        """
        for user in self.factory.users.values():
            if self.username in user.buddylist and self.canContact(user):
                user.buddyUpdate(self)
    def canContact(self,user):
        if self.permitmode==PERMITALL: return 1
        elif self.permitmode==DENYALL: return 0
        elif self.permitmode==PERMITSOME: 
            if user.username in self.permitlist: return 1
            else: return 0
        elif self.permitmode==DENYSOME:
            if user.username in self.denylist: return 0
            else: return 0
        else:
            assert 0,"bad permitmode %s" % self.permitmode
    def buddyUpdate(self,user):
        """
        Update the buddy.  Called from updateUsers()
        """
        if not self.canContact(user): return
        if user in self.factory.users.values(): ol="T"
        else: ol="F"
        if user.idletime:
            idle=int((time.time()-user.idletime)/60)
        else:
            idle=0
        send="UPDATE_BUDDY:%s:%s:%s:%s:%s:%s"%(user.saved.nick,ol,user.saved.evilness,user.signontime,idle,user.userclass)
        self.sendFlap(DATA,send)
    def hearWhisper(self,user,data,auto=0):
        """
        Called when you get an IM.  If auto=1, it's an autoreply from an away message.
        """
        if not self.canContact(user): return
        if auto: auto='T'
        else: auto='F'
        send="IM_IN:%s:%s:%s"%(user.saved.nick,auto,data)
        self.sendFlap(DATA,send)
    def evilFrom(self,user):
        if user=="":
            percent=0.03
        else:
            percent=0.1
        self.saved.evilness=self.saved.evilness+int((100-self.saved.evilness)*percent)
        self.sendFlap(2,"EVILED:%s:%s"%(self.saved.evilness,user))
        self.updateUsers()
    def chatJoin(self,room):
        self.sendFlap(2,"CHAT_JOIN:%s:%s"%(room.id,room.name))
        f="CHAT_UPDATE_BUDDY:%s:T"%room.id
        for u in room.users:
            if u!=self:
                u.chatUserUpdate(room,self)
            f=f+":"+u.saved.nick
        self.sendFlap(2,f)
    def chatInvite(self,room,user,message):
        if not self.canContact(user): return
        self.sendFlap(2,"CHAT_INVITE:%s:%s:%s:%s"%(room.name,room.id,user.saved.nick,message))
    def chatUserUpdate(self,room,user):
        if user in room.users:
            inroom='T'
        else:
            inroom='F'
        self.sendFlap(2,"CHAT_UPDATE_BUDDY:%s:%s:%s"%(room.id,inroom,user.saved.nick))
    def chatMessage(self,room,user,message):
        if not self.canContact(user): return
        self.sendFlap(2,"CHAT_IN:%s:%s:F:%s"%(room.id,user.saved.nick,message))
    def chatLeave(self,room):
        self.sendFlap(2,"CHAT_LEFT:%s"%(room.id))
class Chatroom:
    def __init__(self,fac,exchange,name,id):
        self.exchange=exchange
        self.name=name
        self.id=id
        self.factory=fac
        self.users=[]
    def join(self,user):
        if user in self.users:
            return 
        self.users.append(user)
        user.chatJoin(self)
    def leave(self,user):
        if user not in self.users:
            raise TOCParseError
        self.users.remove(user)
        user.chatLeave(self)
        for u in self.users:
            u.chatUserUpdate(self,user)
        if len(self.users)==0:
            self.factory.remChatroom(self)
    def say(self,user,message):
        for u in self.users:
            u.chatMessage(self,user,message)
class SavedUser:
    def __init__(self):
        self.config=""
        self.nick=""
        self.password=""
        self.evilness=0
class TOCFactory(protocol.Factory):
    def __init__(self):
        self.users={}
        self.savedusers={}
        self.chatroom={}
        self.chatroomid=0
    def buildProtocol(self,addr):
        p=TOC()
        p.factory=self
        return p
    def getChatroom(self,exchange,name):
        for i in self.chatroom.values():
            if normalize(i.name)==normalize(name):
                return i
        self.chatroom[self.chatroomid]=Chatroom(self,exchange,name,self.chatroomid)
        self.chatroomid=self.chatroomid+1
        return self.chatroom[self.chatroomid-1]
    def remChatroom(self,room):
        id=room.id
        del self.chatroom[id]

MAXARGS={}
MAXARGS["CONFIG"]=0
MAXARGS["NICK"]=0
MAXARGS["IM_IN"]=2
MAXARGS["UPDATE_BUDDY"]=5
MAXARGS["ERROR"]=-1
MAXARGS["EVILED"]=1
MAXARGS["CHAT_JOIN"]=1
MAXARGS["CHAT_IN"]=3
MAXARGS["CHAT_UPDATE_BUDDY"]=-1
MAXARGS["CHAT_INVITE"]=3
MAXARGS["CHAT_LEFT"]=0
MAXARGS["ADMIN_NICK_STATUS"]=0
MAXARGS["ADMIN_PASSWD_STATUS"]=0
class TOCClient(protocol.Protocol):
    def __init__(self,username,password,authhost="login.oscar.aol.com",authport=5190):
        
        self.username=normalize(username)
        self._password=password
        self._mode="SendNick"
        self._ourseqnum=0L
        self._authhost=authhost
        self._authport=authport
        self._online=0
        self._buddies=[]
        self._buf=''
    def _debug(self,data):
        print data
    def sendFlap(self,type,data):
        if type==DATA:
            data=data+"\000"
        length=len(data)
        s="*"
        s=s+struct.pack("!BHH",type,self._ourseqnum,length)
        s=s+data
        self._ourseqnum=self._ourseqnum+1
        if self._ourseqnum>(256L**4):
            self._ourseqnum=0
        self._debug((s,length))
        self.transport.write(s)
    def isFlap(self):
        """
        tests to see if a flap is actually on the buffer
        """
        if self._buf=='': return 0
        if self._buf[0]!="*": return 0
        if len(self._buf)<6: return 0
        foo,type,seqnum,length=struct.unpack("!BBHH",self._buf[:6])
        if type not in range(1,6): return 0
        if len(self._buf)<6+length: return 0
        return 1
    def readFlap(self):
        if self._buf=='': return None
        if self._buf[0]!="*":
            raise TOCParseError
        if len(self._buf)<6: return None
        foo,type,seqnum,length=struct.unpack("!BBHH",self._buf[:6])
        if len(self._buf)<6+length: return None
        data=self._buf[6:6+length]
        self._buf=self._buf[6+length:]
        if data[-1]=="\000":
            data=data[:-1]
        return [type,data]
    def connectionMade(self):
        self._debug("connection made! %s" % self.transport)
        self.transport.write("FLAPON\r\n\r\n")
        s="\000\000\000\001\000\001"
        s=s+struct.pack("!H",len(self.username))
        s=s+self.username
        self.sendFlap(1,s)        
    def connectionLost(self):
        self._debug("connection lost!")
        self._online=0
    def dataReceived(self,data):
        self._buf=self._buf+data
        while self.isFlap():
            flap=self.readFlap()
            func=getattr(self,"mode%s"%self._mode)
            self._debug("calling mode%s %s" %(self._mode,func))
            func(flap)
    def modeSendNick(self,flap):
        if flap!=[1,"\000\000\000\001"]: raise TOCParseError
        s="toc_signon %s %s %s %s english \"penguin\""%(self._authhost,\
            self._authport,self.username,roast(self._password))
        self.sendFlap(2,s)
        self._mode="Signon"
    def modeSignon(self,flap):
        if flap!=[2,"SIGN_ON:TOC1.0"]: raise TOCParseError
        self._debug("Whee, signed on!")
        if self._buddies:
            s="toc_add_buddies"
            for i in buddies:
                s=s+" "+normalize(i)
            send.sendFlap(2,s)
        self.sendFlap(2,"toc_init_done")
        self._online=1
        self._mode="Data"
    def modeData(self,flap):
        command,rest=string.split(flap[1],":",1)
        if MAXARGS.has_key(command):
            maxsplit=MAXARGS[command]
        else:
            maxsplit=-1
        if maxsplit==-1:
            l=string.splt(rest,":")
        elif maxsplit==0:
            l=[rest]
        else:
            l=string.split(rest,":",maxsplit)
        try:
            func=getattr(self,"toc%s"%command)
            func(l)
        except:
            self.tocUNKNOWN(command,l)
    def tocUNKNOWN(self,command,data):
        pass
    def tocIM_IN(self,data):
        """
        IM_IN:<user>:<autoreply T|F>:message
        """
        user=data[0]
        autoreply=(data[1]=='T')
        message=data[2]
        self.hearMessage(user,message,autoreply)
    def tocUPDATE_BUDDY(self,data):
        """
        UPDATE_BUDDY:<username>:<online T|F>:<warning level>:<signon time>:<idle time (minutes)>:<user class>
        """
        online=(data[1]=='T')
        away=(data[5][-1]=='U')
        if data[5][-1]=='U':
            data[5]=data[5][:-1]
        self.updateBuddy(online,data[0],data[2],data[3],data[4],data[5],away)
    def tocERROR(self,data):
        code,args=data[0],data[1:]
        self.hearError(code,args)
    def tocEVILED(self,data):
        self.hearWarning(data[0],data[1])
    def hearError(self,code,args):
        """
        called when an error is received
        """
    def hearWarning(self,newamount,user):
        """
        called when we get warned
        user is '' if it's anonymous
        """
    def hearMessage(self,user,message,autoreply):
        """
        called when you receive an IM
        """
    def updateBuddy(self,online,username,evilness,signontime,idletime,away):
        """
        called when a buddy changes state
        """
    def say(self,user,message,autoreply=0):
        if autoreply: a=" auto"
        else: a=''
        self.sendFlap(2,"toc_send_im %s %s%s"%(normalize(user),quote(message),a))
    def away(self,message=''):
        if message: message=' '+message
        self.sendFlap(2,"toc_set_away%s"%message)
        
# ERRORS
# general
NOT_AVAILABLE=901
CANT_WARN=902
MESSAGES_TOO_FAST=903
# admin
BAD_INPUT=911
BAD_ACCOUNT=912
REQUEST_ERROR=913
SERVICE_UNVAILABLE=914
# chat
NO_CHAT_IN=950
# im and info
SEND_TOO_FAST=960
MISSED_BIG_IM=961
MISSED_FAST_IM=962
# directory
DIR_FAILURE=970
TOO_MANY_MATCHES=971
NEED_MORE_QUALIFIERS=972
DIR_UNAVAILABLE=973
NO_EMAIL_LOOKUP=974
KEYWORD_IGNORED=975
NO_KEYWORDS=976
BAD_LANGUAGE=977
BAD_COUNTRY=978
DIR_FAIL_UNKNOWN=979
# authorization
BAD_NICKNAME=980
SERVICE_TEMP_UNAVAILABLE=981
WARNING_TOO_HIGH=982
CONNECTING_TOO_QUICK=983
UNKNOWN_SIGNON=989
