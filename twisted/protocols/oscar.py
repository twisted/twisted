from twisted.protocols import protocol
from twisted.internet import tcp, main
from twisted.python import delay
import struct
import md5
import string
import random
import socket

def SNAC(fam,sub,id,data,flags=[0,0]):
    header="!HHBBL"
    head=struct.pack(header,fam,sub,
                     flags[0],flags[1],
                     id)
    return head+str(data)

def readSNAC(data):
    header="!HHBBL"
    head=list(struct.unpack(header,data[:10]))
    return head+[data[10:]]

def TLV(type,value):
    header="!HH"
    head=struct.pack(header,type,len(value))
    return head+str(value)

def readTLVs(data,count=None):
    header="!HH"
    dict={}
    while data and len(dict)!=count:
        head=struct.unpack(header,data[:4])
        dict[head[0]]=data[4:4+head[1]]
        data=data[4+head[1]:]
    if not count:
        return dict
    return dict,data

def encryptPasswordMD5(password,key):
    m=md5.new()
    m.update(key)
    m.update(password)
    m.update("AOL Instant Messenger (SM)")
    return m.digest()

def encryptPasswordICQ(password):
    key=[0xF3,0x26,0x81,0xC4,0x39,0x86,0xDB,0x92,0x71,0xA3,0xB9,0xE6,0x53,0x7A,0x95,0x7C]
    bytes=map(ord,password)
    r=""
    for i in range(len(bytes)):
        r=r+chr(bytes[i]^key[i%len(key)])
    return r


class OscarConnection(protocol.Protocol):
    def connectionMade(self):
        self.state=""
        self.seqnum=0
        self.buf=''
        self.stopper=None

    def connectionLost(self):
        print "Connection Lost!"
        self.stopKeepAlive()

    def connectionFailed(self):
        print "Connection Failed!"
        self.stopKeepAlive()

    def sendFlap(self,channel,data):
        #print repr((channel,data))
        header="!cBHH"
        self.seqnum=(self.seqnum+1)%0xFFFF
        seqnum=self.seqnum
        head=struct.pack(header,'*', channel,
                         seqnum, len(data))
        self.transport.write(head+str(data))

    def readFlap(self):
        header="!cBHH"
        if len(self.buf)<6: return
        flap=struct.unpack(header,self.buf[:6])
        if len(self.buf)<6+flap[3]: return
        data,self.buf=self.buf[6:6+flap[3]],self.buf[6+flap[3]:]
        return [flap[1],data]

    def dataReceived(self,data):
        self.buf=self.buf+data
        flap=self.readFlap()
        while flap:
            #print flap
            func=getattr(self,"oscar_%s"%self.state,None)
            if not func:
                print "no func for state: %s" % self.state
            state=func(flap)
            if state:
                self.state=state
            flap=self.readFlap()

    def setKeepAlive(self,t):
        self.keepAliveDelay=t
        d=delay.Delayed()
        d.ticktime=1
        self.stopper=d.loop(self.sendKeepAlive,t)
        main.addDelayed(d)

    def sendKeepAlive(self):
        self.sendFlap(0x05,"")

    def stopKeepAlive(self):
        if self.stopper:
            self.stopper.stop()
            self.stopper=None


class SNACBased(OscarConnection):
    def __init__(self,cookie):
        self.cookie=cookie
        self.lastID=0
        self.requestCallbacks={} # request id:[callback,errback]

    def sendSNAC(self,fam,sub,data,callback=None,errback=None,flags=[0,0]):
        reqid=self.lastID
        self.lastID=reqid+1
        if callback or errback:
            if not callback: callback=lambda x: None
            if not errback: errback=lambda x: None
        if callback:
            self.requestCallbacks[reqid]=[callback,errback]
        #print [fam,sub,data]
        self.sendFlap(0x02,SNAC(fam,sub,reqid,data))
        return reqid

    def oscar_(self,data):
        self.sendFlap(0x01,"\000\000\000\001"+TLV(6,self.cookie))
        return "Data"

    def oscar_Data(self,data):
        snac=readSNAC(data[1])
        #print snac
        if self.requestCallbacks.has_key(snac[4]):
            callback,errback=self.requestCallbacks[snac[4]]
            del self.requestCallbacks[snac[4]]
            if snac[1]!=1:
                callback(snac)
            else:
                errback(snac)
            return
        func=getattr(self,"oscar_%02X_%02X"%(snac[0],snac[1]),None)
        if not func:
            self.oscar_unknown(snac)
        else:
            func(snac[2:])
        return "Data"

    def oscar_unknown(self,snac): print "unknown",snac


class BOSConnection(SNACBased):
    def __init__(self,username,cookie):
        SNACBased.__init__(self,cookie)
        self.username=username
        self.screenname=None
        self.evilness=None
        self.userInfo=""
        self.awayMessage=""
        self.groups=[]
        self.groupDict={}
        self.onlineFlag=0

        self.capabilities=CAP_IMAGE+CAP_CHAT

        self.directConnections = {} # user: DirectConnection
        
        self.chatService=None
        
        self.waitingChats={} # request id:[chatname,invite message]

        self.waitingForInfo={} # request id: username
        self.waitingForAway={} # request id: username
        self.userInfos={} # user: info/away

    def parseUser(self,data,count=None):
        l=ord(data[0])
        screenname=data[1:1+l]
        warn,foo=struct.unpack("!HH",data[1+l:5+l])
        warn=int(warn)
        tlvs=data[5+l:]
        if count:
            tlvs,rest=readTLVs(tlvs,foo)
            return (screenname,warn,tlvs),rest
        return (screenname,warn,readTLVs(tlvs))

    def oscar_01_03(self,snac):
        self.sendSNAC(0x01,0x17,"\x00\x01\x00\x03\x00\x13\x00\x01\x00\x02\x00\x01\x00\x03\x00\x01\x00\x04\x00\x01\x00\x06\x00\x01\x00\x08\x00\x01\x00\x09\x00\x01\x00\x0a\x00\x01\x00\x0B\x00\x01\x00\x0C\x00\x01")
        
    def oscar_01_07(self,snac):
        self.sendSNAC(0x01,0x08,"\x00\x01\x00\x02\x00\x03\x00\x04\x00\x05")
        self.sendSNAC(0x01,0x0e,"")
        self.sendSNAC(0x13,0x02,"")
        self.sendSNAC(0x13,0x05,"\x00"*6)
        self.sendSNAC(0x02,0x02,"")
        self.sendSNAC(0x03,0x02,"")
        self.sendSNAC(0x04,0x04,"")
        self.sendSNAC(0x09,0x02,"")

    def oscar_01_0F(self,snac):
        l=ord(snac[3][0])
        self.screenName=snac[3][1:1+l]
        warn,foo=struct.unpack("!HH",snac[3][1+l:5+l])
        self.warningLevel=int(warn)
        tlvs=snac[3][5+l:]
#        print self.screenName,self.warningLevel,readTLVs(tlvs)

    def oscar_01_13(self,snac):
        self.sendSNAC(0x01,0x06,"")

    def oscar_01_18(self,snac): pass

    def oscar_02_03(self,snac): pass

    def oscar_03_03(self,snac): pass

    def oscar_03_0B(self,snac):
        user=self.parseUser(snac[3])
        statenumber=struct.unpack("!H",user[2][1])[0]
        state=""
        accounttype=""
        if statenumber&1:
            accounttype="Unconfirmed Internet"
            statenumber=statenumber^1
        elif statenumber&16:
            accounttype="Internet"
            statenumber=statenumber^16
        elif statenumber&4:
            accounttype="AOL"
            statenumber=statenumber^16
        if statenumber==32: state="Away"
        else: state="Online"
        caps=[]
        if user[2].has_key(13): # caps
            t=user[2][13]
            while t:
                c=t[:16]
                if c==CAP_ICON: caps.append("icon")
                elif c==CAP_IMAGE: caps.append("image")
                elif c==CAP_VOICE: caps.append("voice")
                elif c==CAP_CHAT: caps.append("chat")
                elif c==CAP_GET_FILE: caps.append("getfile")
                elif c==CAP_SEND_FILE: caps.append("sendfile")
                elif c==CAP_SEND_LIST: caps.append("sendlist")
                elif c==CAP_GAMES: caps.append("games")
                else: caps.append(("unknown",c))
                t=t[16:]
#        if not caps: return
        caps.sort()
        if user[2].has_key(4):
            idle=struct.unpack("!H",user[2][4])[0]
        else:
            idle=0
        self.updateUser(user[0],state,accounttype,user[1]/10,idle,caps)

    def oscar_03_0C(self,snac):
        user=self.parseUser(snac[3])
        self.updateUser(user[0],"Offline","",0,0,[])

    def oscar_04_05(self,snac): pass

    def oscar_04_07(self,snac):
        user,rest=self.parseUser(snac[3][10:],1)
        if rest[:2]=='\000\002':
            self.gotMessage(user[0],rest[19:-14])
            if self.awayMessage:
                self.sendAutoReply(user[0],'<font color="#0000ff">'+self.awayMessage)
        elif rest[:2]=='\000\004': # away message
            self.gotAutoReply(user[0],rest[57:])
        elif rest[:2]=='\000\005':
            self.sendAutoReply(user[0],'<font color="#0000ff">'+self.awayMessage)
            cap=rest[14:30]
            tlvs=readTLVs(rest[30:])
            if cap==CAP_IMAGE: # direct connection
                if tlvs.has_key(11): # cancel
                    self.imageCancel(user[0])
                else:
                    port=struct.unpack("!H",tlvs[5])[0]
                    ip=string.join(map(str,map(ord,tlvs[4])),".")
                    self.imageGotRequest(user[0],ip,port)
            else:
                print repr(rest)
        else:
            print user,repr(rest)

    def oscar_04_0C(self,snac): pass

    def oscar_09_02(self,snac):
        self.error(snac[3])

    def oscar_09_03(self,snac): pass

    def oscar_0B_02(self,snac):
        t=struct.unpack("!H",snac[3])[0]
        self.setKeepAlive(t)

    def oscar_13_03(self,snac): pass

    def oscar_13_06(self,snac): # buddy list
        revision=struct.unpack("!H",snac[3][1:3])
        rest=snac[3][3:]
        groups=self.groups
        permit=[]
        deny=[]
        dict=self.groupDict
        mode=""
        while len(rest)>4:
            l=struct.unpack("!H",rest[:2])[0]
            name=rest[2:2+l]
            gid,bid,flag,addl=struct.unpack("!4H",rest[2+l:10+l])
            tlvs=readTLVs(rest[10+l:10+l+addl])
            if gid and flag==1 and not dict.has_key(gid):
                dict[gid]=len(groups)
                groups.append((name,[]))
            elif gid and flag==0:
                groups[dict[gid]][1].append(name)
            elif flag==2:
                if not mode: mode="permitlist"
                permit.append(name)
            elif flag==3:
                if not mode: mode="denylist"
                deny.append(name)
            elif flag==4:
                if tlvs.has_key(202):
                    if tlvs[202]=='\001':
                        mode="permitall"
                    elif tlvs[202]=='\002':
                        mode="denyall"
#                    else:
#                        print name,gid,bid,flag,tlvs
#                else:
#                    print name,gid,bid,flag,tlvs
            elif flag==5:
                if tlvs.has_key(200) and tlvs[200]=='\000\000\004\000':
                    mode="permitbuddies"
#                else:
#                    print name,gid,bid,flag,tlvs
#            else:
#                print name,gid,bid,flag,tlvs
            rest=rest[10+l+addl:]
        self.sendSNAC(0x13,0x07,"")
        self.groups=groups
        self.groupDict=dict
        self.gotBuddyList(groups,mode,permit,deny)
        #self.sendFlap(2,SNAC(0x13,0x13,0x13,""))

    def oscar_13_0F(self,snac):
        self.sendSNAC(0x13,0x07,"")
        self.gotBuddyList([],[],[])
       
    # called functions
    def setInfo(self,info):
        self.userInfo=info
        self.sendSNAC(0x02,0x04,
                             TLV(1,'text/x-aolrtf; charset="us-ascii"')+
                             TLV(2,self.userInfo)+
                             TLV(3,'text/x-aolrtf; charset="us-ascii"')+
                             TLV(4,self.awayMessage)+
                             TLV(5,self.capabilities)) # capabilities here

    def away(self,away):
        self.awayMessage=away
        self.sendSNAC(0x02,0x04,
                             TLV(1,'text/x-aolrtf; charset="us-ascii"')+
                             TLV(2,self.userInfo)+
                             TLV(3,'text/x-aolrtf; charset="us-ascii"')+
                             TLV(4,self.awayMessage)+
                             TLV(5,CAP_CHAT+CAP_IMAGE)) # capabilities here

    def online(self):
        if self.onlineFlag: return
        self.sendSNAC(0x01,0x02,"\x00\x01\x00\x03\x01\x10\x04\x7b\x00\x13\x00\x01\x01\x10\x04\x7b\x00\x02\x00\x01\x01\x01\x04\x7b\x00\x03\x00\x01\x01\x10\x04\x7b\x00\x04\x00\x01\x01\x10\x04\x7b\x00\x06\x00\x01\x01\x10\x04\x7b\x00\x08\x00\x01\x01\x04\x00\x01\x00\x09\x00\x01\x01\x10\x04\x7b\x00\x0a\x00\x01\x01\x10\x04\x7b\x00\x0b\x00\x01\x01\x00\x00\x01\x00\x0c\x00\x01\x01\x04\x00\x01")
        self.onlineFlag=1

    def sendIM(self,user,message):
        if self.directConnections.has_key(user):
            self.directConnections[user].sendMessage(message)
            return
        self.sendSNAC(0x04,0x06,
                             "\x3c\x35\x46\x4a\x36\x31\x00\x78\x00\x01"+
                             chr(len(user))+
                             user+
                             "\000\002"+
                             struct.pack("!H",len(message)+15)+
                             "\005\001\000\003\001\001\002\001\001"+
                             struct.pack("!H",len(message)+4)+
                             "\000\000\000\000"+
                             message)

    def sendAutoReply(self,user,reply):
                self.sendSNAC(0x04,0x06,
                             "\x3c\x35\x46\x4a\x36\x31\x00\x78\x00\x01"+
                             chr(len(user))+
                             user+
                             "\000\002"+
                             struct.pack("!H",len(reply)+15)+
                             "\005\001\000\003\001\001\002\001\001"+
                             struct.pack("!H",len(reply)+4)+
                             "\000\000\000\000"+
                             reply+
                             "\000\004\000\000")

    def joinChat(self,room):
        if not self.chatService:
            def callback(snac,room=room,self=self):
                tlvs=readTLVs(snac[5])
                cookie=tlvs[6]
                serverip=tlvs[5]
                self.chatService=ChatService(self,cookie)
                self.chatService.joinChat(room)
                tcp.Client(serverip,5190,self.chatService)
            self.sendSNAC(0x01,0x04,"\x00\x0d",callback) # ask for chat service
        else:
            self.chatService.joinChat(group)

    def leaveChat(self,room):
        self.chatService.leaveChat(room)

    def chatSendMessage(self,room,message):
        self.chatService.sendMessage(room,message)
            
    def getInfo(self,user):
        reqid=self.sendSNAC(0x02,0x05,"\000\001"+chr(len(user))+user
                            ,self.userInfoCallback,self.userInfoErrback)
        self.waitingForInfo[reqid]=user
        reqid=self.sendSNAC(0x02,0x05,"\000\003"+chr(len(user))+user
                            ,self.userAwayCallback,self.userAwayErrback)
        self.waitingForAway[reqid]=user

    def userInfoCallback(self,snac):
        try:
            userinfo=self.parseUser(snac[5])[2][2]
        except KeyError:
            userinfo="Note: AOL member profiles are not accessible through AOL Instant Messenger."
        username=self.waitingForInfo[snac[4]]
        del self.waitingForInfo[snac[4]]
        if self.userInfos.has_key(username):
            self.gotUserInfo(username,userinfo,self.userInfos[username])
            del self.userInfos[username]
        else:
            self.userInfos[username]=userinfo

    def userInfoErrback(self,snac):
        username=self.waitingForInfo[snac[4]]
        del self.waitingForInfo[snac[4]]
        if self.userInfos.has_key(username):
            self.gotUserInfo(username,None,self.userInfos[username])
            del self.userInfos[username]
        else:
            self.userInfos[username]=None

    def userAwayCallback(self,snac):
        user=self.parseUser(snac[5])
        if user[2].has_key(4):
            useraway=self.parseUser(snac[5])[2][4]
        else:
            useraway=""
        username=self.waitingForAway[snac[4]]
        del self.waitingForAway[snac[4]]
        if self.userInfos.has_key(username):
            self.gotUserInfo(username,self.userInfos[username],useraway)
            del self.userInfos[username]
        else:
            self.userInfos[username]=useraway

    def userAwayErrback(self,snac):
        username=self.waitingForAway[snac[4]]
        del self.waitingForAway[snac[4]]
        if self.userInfos.has_key(username):
            self.gotUserInfo(username,self.userInfos[username],None)
            del self.userInfos[username]
        else:
            self.userInfos[username]=None

    def imageAskConnect(self,user):
#        if not self.directConnectionServer:
#            self.directConnectionServer=DirectConnectionServer(self)
#        if self.directConnections.has_key(user):
#            self.directConnections[user]=self.directConnectionServer
#            tcp.Server("localhost",5190,self.directConnections[user])
        self.sendSNAC(0x04,0x06,
                      "\x3c\x35\x46\x4a\x00\x0a\xdb\xae\x00\x02"+
                      chr(len(user))+
                      user+
                      "\000\005\000\062\000\000"+
                      "\000"*8+
                      CAP_IMAGE+
                      TLV(0x0a,"\000\001")+
                      TLV(0x0F,"")+
                      TLV(0x04,socket.inet_aton(socket.gethostbyname(socket.gethostname())))+
                      TLV(0x05,"\024\106")+
                      TLV(0x03,""),self.imageAcceptCallback)

    def imageAcceptCallback(self,snac):
        #print snac
        pass

    def imageAccept(self,user,ip,port):
        self.sendSNAC(0x04,0x06,
                      "\x3c\x35\x46\x4a\x00\x0a\xdb\xae\00\x02"+
                      chr(len(user))+
                      user+
                      "\000\005\000\062\000\000"+
                      "\000"*8+
                      CAP_IMAGE+
                      TLV(0x0a,"\000\002")+
                      TLV(0x0F,"")+
                      TLV(0x04,socket.inet_aton(socket.gethostbyname(socket.gethostname())))+
                      TLV(0x05,"\121\106")+
                      TLV(0x03,""))
        self.directConnections[user]=DirectConnection(self)
        tcp.Client(ip,4443,self.directConnections[user])

    # callback
    def error(self,url): print url

    def updateUser(self,screenname,state,accounttype,warning,idle,caps):
        print screenname,state,accounttype,warning,idle

    def gotMessage(self,user,message):
        print user,message
        #if not self.directConnections.has_key(user): self.imageAskConnect(user)
        #self.sendIM(user,message)

    def gotAutoReply(self,user,reply):
        print user,"autoreply",reply

    def gotUserInfo(self,user,info,away):
        print user,info,away

    def gotBuddyList(self,groups,mode,permit,deny):
        print groups,mode,permit,deny
        self.setInfo("I am a wicked Twisted user!")
        self.online()

    def chatJoined(self,room):
        print "chat joined",room

    def chatLeft(self,room):
        print "chat left", room

    def chatGotMembers(self,room,users):
        print "chat members",room,users

    def chatMemberJoined(self,room,user):
        print "chat member joined",room,user

    def chatMemberLeft(self,room,user):
        print "chat member left",room,user

    def chatMessage(self,room,user,message):
        print "chat message",room,user,message

    def imageCancel(self,user):
        print "image cancel",user

    def imageGotRequest(self,user,ip,port):
        print "image request",user,ip,port
        self.imageAccept(user,ip,port)

    def imageGotMessage(self,user,message):
        self.gotMessage(user,message)
    

class ICQConnection(SNACBased):
    def __init__(self,uin,cookie):
        SNACBased.__init__(cookie)
        self.uin=uin

    def oscar_01_03(self,snac):
        self.sendSNAC(0x01,0x17,'\x00\x01\x00\x03\x00\x13\x00\x02\x00\x02\x00\x01\x00\x03\x00\x01\x00\x15\x00\x01\x00\x04\x00\x01\x00\x06\x00\x01\x00\x09\x00\x01\x00\x0A\x00\x01\x00\x0B\x00\x01')

    def oscar_01_07(self,snac):
        self.sendSNAC(0x01,0x08,"\x00\x01\x00\x02\x00\x03\x00\x04\x00\x05")
        self.sendSNAC(0x01,0x0E,"")
        self.sendSNAC(0x13,0x02,"")
        self.sendSNAC(0x13,0x05,"\x3C\x5C\x36\x28\x00\x04")
        self.sendSNAC(0x02,0x02,"")
        self.sendSNAC(0x03,0x02,"")
        self.sendSNAC(0x04,0x04,"")
        self.sendSNAC(0x09,0x02,"")

    def oscar_01_0F(self,snac): pass

    def oscar_01_18(self,snac):
        self.sendSNAC(0x01,0x06,"")

    def oscar_02_03(self,snac): pass

    def oscar_04_05(self,snac): pass

    def oscar_09_03(self,snac): pass

    def oscar_13_03(self,snac): pass

    def oscar_13_0F(self,snac):
        self.sendSNAC(0x13,0x07,"")
        self.sendSNAC(0x02,0x04,"\x00\x00")
        self.sendSNAC(0x04,0x02,"\x00\x00\x00\x00\x00\x03\x1F\x40\x03\xE7\x03\xE7\x00\x00\x00\x00")
        self.sendSNAC(0x01,0x1E,
                      TLV(0x06,"\x20\x03\x00\x00")+
                      TLV(0x08,"\x00\x00")+
                      TLV(0x0C,"\x42\x2C\x69\x25\x00\x00\x23\x56\x02\x00\x08\x64\x92\x40\x3C\x00\x00\x00\x50\x00\x00\x00\x03\x3C\x5C\x69\xFD\x3C\x5C\x69\x8F\x3C\x5Cv69\x8F\x00\x00"))
        self.sendSNAC(0x01,0x02,"\x00\x01\x00\x03\x01\x10\x04\x7B\x00\x13\x00\x02\x01\x10\x04\x7B\x00\x02\x00\x01\x01\x01\x04\x7B\x00\x03\x00\x01\x01\x10\x04\x7B\x00\x15\x00\x01\x01\x10\x04\x7B\x00\x04\x00\x01\x01\x10\x04\x7B\x00\x06\x00\x01\x01\x10\x04\x7B\x00\x09\x00\x01\x01\x10\x04\x7B\x00\x0A\x00\x01\x01\x10\x04\x7B\x00\x0B\x00\x01\x01\x10\x04\x7B")
        self.sendSNAC(0x15,0x02,"\x00\x01\x00\x0A\x08\x00\x0E\x87\xE8\x08\x3C\x00\x02\x00")

    def oscaR_15_02(self,snac): pass


class ChatService(SNACBased):
    def __init__(self,bos,cookie):
        SNACBased.__init__(self,cookie)
        self.bos=bos
        self.online=0
        self.joins=[]
        self.roomConnections={}

    def oscar_01_03(self,snac):
        self.sendSNAC(0x01,0x17,"\000\001\000\003\000\015\000\001")

    def oscar_01_07(self,snac):
        self.sendSNAC(0x01,0x08,"\000\001\000\002\000\003\000\004\000\005")
        self.sendSNAC(0x0d,0x02,"")

    def oscar_01_18(self,snac):
        self.sendSNAC(0x01,0x06,"")
        self.setKeepAlive(300)

    def oscar_0D_09(self,snac):
        if not self.online:
            self.sendSNAC(0x01,0x02,"\000\001\000\003\000\020\004{\000\015\000\001\000\020\004{")
            self.online=1
            for j in self.joins:
                self.joinChat(j)
            self.joins=[]
        else:
            urllen=ord(snac[3][6])
            url=snac[3][7:7+urllen]
            tlvs=readTLVs(snac[3][6+urllen:])
            def callback(snac,self=self,room=tlvs[211]):
                tlvs=readTLVs(snac[5])
                cookie=tlvs[6]
                serverip=tlvs[5]
                self.roomConnections[room]=ChatRoomConnection(self.bos,room,cookie)
                tcp.Client(serverip,5190,self.roomConnections[room])
            self.bos.sendSNAC(0x01,0x04,"\x00\x0e\x00\x01\x00 \x00\x04\x1b"+url+"\x00\x00",callback)

    def room(self,room): return self.roomConnections[room]    

    def joinChat(self,room):
        if not self.online:
            self.joins.append(room)
            return
        self.sendSNAC(0x0d,0x08,"\000\004\006create\377\377\001\000\003"+
                            TLV(0xd7,"en")+
                            TLV(0xd6,"us-ascii")+
                            TLV(0xd3,room))
    def leaveChat(self,room):
        self.room(room).transport.loseConnection()

    def sendMessage(self,room,message):
        self.room(room).sendMessage(message)
        

class ChatRoomConnection(SNACBased):
    def __init__(self,bos,room,cookie):
        SNACBased.__init__(self,cookie)
        self.bos=bos
        self.room=room

    def oscar_01_03(self,snac):
        self.sendSNAC(0x01,0x17,"\000\001\000\003\000\015\000\001")

    def oscar_01_07(self,snac):
        self.sendSNAC(0x01,0x08,"\000\001\000\002\000\003\000\004\000\005")
        self.sendSNAC(0x01,0x02,"\000\001\000\003\000\020\004{\000\016\000\001\000\020\004{")

    def oscar_01_18(self,snac):
        self.sendSNAC(0x01,0x06,"")
        self.setKeepAlive(300)
        self.bos.chatJoined(self.room)

    def oscar_0E_02(self,snac):
        pass

    def oscar_0E_03(self,snac):
        users=[]
        rest=snac[3]
        while rest:
            l=ord(rest[0])
            name=rest[1:1+l]
            foo,count=struct.unpack("!HH",rest[1+l:5+l])
            tlvs,rest=readTLVs(rest[5+l:],count)
            users.append(name)
        if len(users)>1:
            self.bos.chatGotMembers(self.room,users)
        else:
            self.bos.chatMemberJoined(self.room,users[0])

    def oscar_0E_04(self,snac):
        user=self.bos.parseUser(snac[3])
        self.bos.chatMemberLeft(self.room,user[0])

    def oscar_0E_06(self,snac):
        user,warn,tlvs=self.bos.parseUser(snac[3][14:])
        message=readTLVs(tlvs[5])[1]
        self.bos.chatMessage(self.room,user,message)

    def sendMessage(self,message):
        tlvs=TLV(0x02,"us-ascii")+TLV(0x03,"en")+TLV(0x01,message)
        self.sendSNAC(0x0e,0x05,
                      "\x46\x30\x38\x30\x44\x00\x63\x00\x00\x03\x00\x01\x00\x00\x00\x06\x00\x00\x00\x05"+
                      struct.pack("!H",len(tlvs))+
                      tlvs)

       
class DirectConnection(protocol.Protocol):
    def __init__(self,bos):
        self.bos=bos
        self.buf=''
        self.buffered=1
        self.mode="Message"

    def sendMessage(self,message,pad=""):
        t="ODC2"
        t=t+struct.pack("!H",0x4c+len(pad))
        t=t+"\000\001\000\006\000\000"
        t=t+"\000"*16
        t=t+struct.pack("!L",len(message))
        t=t+"\000"*12
        t=t+self.bos.screenName
        t=t+"\000"*(32-len(self.bos.screenName))
        t=t+message
        self.transport.write(t)

    def dataReceived(self,data):
        self.buf=self.buf+data
        if len(self.buf)<6: return
        l=struct.unpack("!H",self.buf[4:6])[0]
        if len(self.buf)<l: return
        things=struct.unpack("!HHHLLLLLLLL",self.buf[6:44])
        lmsg=things[7]
        if len(self.buf)<l+lmsg: return
        user=self.buf[44:76]
        luser=string.find(user,"\000")
        user=user[:luser]
        if l>76:
            pad=self.buf[76:l]
        message=self.buf[l:l+lmsg]
        self.buf=self.buf[l+lmsg:]
        if message:
            self.bos.imageGotMessage(user,message)


class DirectConnectionServer(protocol.Factory):
    def __init__(self,bos):
        self.protocol=lambda x,bos=bos:DirectConnection(bos)


class OscarAuthenticator(OscarConnection):
    BOSClass = BOSConnection
    def __init__(self,username,password,callback=None,icq=0):
        self.username=username
        self.password=password
        self.callback=callback
        self.icq=icq # icq mode
        if icq and self.BOSClass==BOSConnection:
            self.BOSClass=ICQConnection

    def oscar_(self,flap):
        if not self.icq:
            self.sendFlap(FLAP_CHANNEL_NEW_CONNECTION,"\000\000\000\001")
            self.sendFlap(FLAP_CHANNEL_DATA,
                          SNAC(0x17,0x06,0,
                               TLV(TLV_USERNAME,self.username)))
            self.state="Key"
        else:
            encpass=encryptPasswordICQ(self.password)
            self.sendFlap(FLAP_CHANNEL_NEW_CONNECTION,
                          '\000\000\000\001'+
                          TLV(0x01,self.username)+
                          TLV(0x02,encpass)+
                          TLV(0x03,'ICQ Inc. - Product of ICQ (TM).2001b.5.15.1.3638.85')+
                          TLV(0x16,"\x01\x0a")+
                          TLV(0x17,"\x00\x05")+
                          TLV(0x18,"\x00\x12")+
                          TLV(0x19,"\000\001")+
                          TLV(0x1a,"\x0eK")+
                          TLV(0x14,"\x00\x00\x00U")+
                          TLV(0x0f,"en")+
                          TLV(0x0e,"us"))
            self.state="Cookie"

    def oscar_Key(self,data):
        snac=readSNAC(data[1])
        key=snac[5][2:]
        encpass=encryptPasswordMD5(self.password,key)
        self.sendFlap(FLAP_CHANNEL_DATA,
                      SNAC(0x17,0x02,0,
                           TLV(TLV_USERNAME,self.username)+
                           TLV(TLV_PASSWORD,encpass)+
                           TLV(TLV_CLIENTNAME,"AOL Instant Messenger (SM), version 4.7.2468/WIN32")+
                           TLV(TLV_RANDOM1,"\x01\x09")+
                           TLV(TLV_CLIENTMAX,"\000\004")+
                           TLV(TLV_CLIENTMIN,"\000\007")+
                           TLV(TLV_RANDOM2,"\000\000")+
                           TLV(TLV_CLIENTSUB,"\x09\xa4")+
                           TLV(TLV_RANDOM3,"\x00\x00\x00\x9e")+
                           TLV(TLV_LANG,"en")+
                           TLV(TLV_COUNTRY,"us")+
                           TLV(TLV_RANDOM4,"\001")))
        return "Cookie"

    def oscar_Cookie(self,data):
        snac=readSNAC(data[1])
        if self.icq:
            i=snac[5].find("\000")
            snac[5]=snac[5][i:]
        tlvs=readTLVs(snac[5])
        if tlvs.has_key(6):
            self.cookie=tlvs[6]
            server,port=string.split(tlvs[5],":")
            bos=self.BOSClass(self.username,self.cookie)
            if self.callback: self.callback(bos)
            tcp.Client(server,int(port),bos)
            self.transport.loseConnection()
        elif tlvs.has_key(8):
            errorcode=tlvs[8]
            errorurl=tlvs[4]
            if errorcode=='\000\030':
                error="You are attempting to sign on again too soon.  Please try again later."
            elif errorcode=='\000\005':
                error="Invalid Username or Password."
            else: error=errorcode
            self.error(error,errorurl)
        else:
            print tlvs
        return "None"

    def oscar_None(self,data): pass

    def error(self,error,url):
        print "ERROR!",error,url
        self.transport.loseConnection()

FLAP_CHANNEL_NEW_CONNECTION = 0x01
FLAP_CHANNEL_DATA = 0x02
FLAP_CHANNEL_ERROR = 0x03
FLAP_CHANNEL_CLOSE_CONNECTION = 0x04
FLAPS={
    FLAP_CHANNEL_NEW_CONNECTION:'NewConnection',
    FLAP_CHANNEL_DATA:'Data',
    FLAP_CHANNEL_ERROR:'Error',
    FLAP_CHANNEL_CLOSE_CONNECTION:'CloseConnection'
}

TLV_USERNAME = 0x01
TLV_CLIENTNAME = 0x03
TLV_COUNTRY = 0x0E
TLV_LANG = 0x0F
TLV_RANDOM3 = 0x14
TLV_RANDOM1 = 0x16
TLV_CLIENTMAX = 0x17
TLV_CLIENTMIN = 0x18
TLV_RANDOM2 = 0x19
TLV_CLIENTSUB = 0x1A
TLV_PASSWORD = 0x25
TLV_RANDOM4 = 0x4a

CAP_ICON = '\011F\023FL\177\021\321\202"DEST\000\000'
CAP_VOICE = '\011F\023AL\177\021\321\202"DEST\000\000'
CAP_IMAGE = '\011F\023EL\177\021\321\202"DEST\000\000'
CAP_CHAT = 't\217$ b\207\021\321\202"DEST\000\000'
CAP_GET_FILE = '\011F\023HL\177\021\321\202"DEST\000\000'
CAP_SEND_FILE = '\011F\023CL\177\021\321\202"DEST\000\000'
CAP_GAMES = '\011F\023GL\177\021\321\202"DEST\000\000'
CAP_SEND_LIST = '\011F\023KL\177\021\321\202"DEST\000\000'