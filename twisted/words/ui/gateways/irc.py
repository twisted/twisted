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

from twisted.protocols import irc
from twisted.words.ui import gateway
from twisted.internet import tcp
import string
import time

shortName="IRC"
longName="Internet Relay Chat"

loginOptions=[["text","Nickname","username","my_nickname"],
              ["text","Real Name","realname","Twisted User"],
              ["text","Password (optional)","password",""],
              ["text","Server","server","localhost"],
              ["text","Port #","port","6667"]]

def makeConnection(im,server=None,port=None,**kw):
    c=apply(IRCGateway,(),kw)
    c.attachIM(im)
    try:
        port=int(port)
    except:
        pass
    tcp.Client(server,port,c)

class IRCGateway(irc.IRCClient,gateway.Gateway):

    protocol=shortName

    def __init__(self,username=None,password="",realname=""):
        gateway.Gateway.__init__(self)
        self._namreplies={}
        self.logonUsername=username
        self.nickname=username
        self.name="%s (%s)"%(username,self.protocol)
        self.password=password
        self.realname=realname
        self._ingroups={}
        self._groups={}

    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        if self.password: self.sendLine("PASS :%s"%self.password)
        self.setNick(self.logonUsername)
        self.sendLine("USER %s foo bar :%s"%(self.nickname,self.realname))

    def connectionFailed(self):
        self.im.send(self,"error",message="Connection Failed!")
        self.detachIM()

    def connectionLost(self):
        self.im.send(self,"error",message="Connection lost.")
        self.detachIM()

    def loseConnection(self):
#        for g in self._ingroups[self.nickname]:
#            self.part(g)
        self.sendLine("QUIT :Goodbye!")
        self.transport.loseConnection()

    def setNick(self,nick):
        self.username=nick
        irc.IRCClient.setNick(self,nick)

    def event_addContact(self,contact):
        pass

    def event_removeContact(self,contact):
        pass

    def event_changeStatus(self, status):
        if status=="Online":
            self.setNick(self.logonUsername)
            self.away('')
        elif status=="Away":
            self.away("I'm not here right now.  Leave a message.")
            self.setNick(self.logonUsername+"|away")

    def event_joinGroup(self,group):
        if self._groups.has_key(string.lower(group)):
            return
        self.join(group)
        self._groups[string.lower(group)]=group
        self.joinedGroup(group)

    def event_leaveGroup(self,group):
        self.leave(group)
        self.leftGroup(group)

    def event_getGroupMembers(self,group):
        pass # this gets automatically done

    def event_directMessage(self,user,message):
        self.msg(user,message)

    def event_groupMessage(self,group,message):
        self.say(group,message)

    def irc_RPL_NAMREPLY(self,prefix,params):
        """
        RPL_NAMREPLY
        >> NAMES #bnl
        << :Arlington.VA.US.Undernet.Org 353 z3p = #bnl :pSwede Dan-- SkOyg AG
        """
        channel=string.lower(params[2][1:])
        users=string.split(params[3])
        for ui in range(len(users)):
            while users[ui][0] in ["@","+"]: # channel modes
                users[ui]=users[ui][1:]
        if not self._namreplies.has_key(channel):
            self._namreplies[channel]=[]
        self._namreplies[channel].extend(users)
        for nickname in users:
            try:
                self._ingroups[nickname].append(channel)
            except:
                self._ingroups[nickname]=[channel]

    def irc_RPL_ENDOFNAMES(self,prefix,params):
        group=params[1][1:]
        self.receiveGroupMembers(self._namreplies[string.lower(group)],group)
        del self._namreplies[string.lower(group)]

    def irc_RPL_AWAY(self,prefix,params):
        nickname=params[1]
        message=params[2]
        self.receiveDirectMessage(nickname,"AWAY: %s"%message)

    def irc_RPL_TOPIC(self,prefix,params):
        self.im.send(self,"receiveGroupTopic",group=params[1][1:],topic=params[2])
        

    def irc_NICK(self,prefix,params):
        oldname=string.split(prefix,"!")[0]
        if self._ingroups.has_key(oldname):
            self._ingroups[params[0]]=self._ingroups[oldname]
            del self._ingroups[oldname]
        self.notifyNameChanged(oldname,params[0])

    def irc_JOIN(self,prefix,params):
        nickname=string.split(prefix,"!")[0]
        group=self._groups[string.lower(params[0][1:])]
        if nickname!=self.nickname:
            try:
                self._ingroups[nickname].append(group)
            except:
                self._ingroups[nickname]=[group]
            self.memberJoined(nickname,group)

    def irc_PART(self,prefix,params):
        nickname=string.split(prefix,"!")[0]
        group=self._groups[string.lower(params[0][1:])]
        if nickname!=self.nickname:
            if group in self._ingroups[nickname]:
                self._ingroups[nickname].remove(group)
                self.memberLeft(nickname,group)
            else:
                print "%s left %s, but wasn't in the room."%(nickname,group)
        else:
            del self._groups[string.lower(group)]

    def irc_QUIT(self,prefix,params):
        nickname=string.split(prefix,"!")[0]
        for g in self._ingroups[nickname]:
            self.memberLeft(nickname,g)
        self._ingroups[nickname]=[]

    def privmsg(self,user,channel,message):
        nickname=string.split(user,"!")[0]
        if channel[0]=="#": # channel
            group=self._groups[string.lower(channel[1:])]
            self.receiveGroupMessage(nickname,group,message)
        else:
            self.receiveDirectMessage(nickname,message)

    def action(self, user, channel, data):
        group=self._groups[string.lower(channel[1:])]
        nickname=string.split(user,"!")[0]
        self.receiveGroupEmote(nickname,group,data)

    def irc_RPL_WHOISUSER(self,prefix,params):
        """
        >>>WHOIS z3pfoo
        <<<:sagan.openprojects.net 311 z3pfoo z3pfoo z3p 66-44-50-121.s121.tnt6.lnhdc.md.di
alup.rcn.com * :z3p
        <<<:sagan.openprojects.net 312 z3pfoo z3pfoo sagan.openprojects.net :New York, US
        <<<:sagan.openprojects.net 317 z3pfoo z3pfoo 67 1002978040 :seconds idle, signon ti
me
        <<<:sagan.openprojects.net 318 z3pfoo z3pfoo :End of /WHOIS list.
        """
        ircname=params[1]
        username=params[2]
        hostname=params[3]
        name=params[5]
        self.receiveDirectMessage("**irc**","%s (%s@%s) : %s" % (ircname,
                                    username,hostname,name))

    def irc_RPL_WHOISSERVER(self,prefix,params):
        ircname=params[1]
        server=params[2]
        serverinfo=params[3]
        self.receiveDirectMessage("**irc**","%s on server %s (%s)" % (ircname,
                                    server,serverinfo))

    def irc_RPL_WHOISOPERATOR(self,prefix,params):
        ircname=params[2]
        self.receiveDirectMessage("**irc**","%s is an IRC operator" % (ircname))

    def irc_RPL_WHOISIDLE(self,prefix,params):
        ircname=params[1]
        parts=string.split(params[-1],', ')
        foo=[]
        for i in range(len(parts)):
            if parts[i]=="signon time":
                t=time.ctime(int(params[i+2]))
            else:
                t=params[i+2]
            foo.append(t+" "+parts[i])
        foo=string.join(foo,", ")
        if foo:
            self.receiveDirectMessage("**irc**", "%s is %s" % (ircname, foo))

    def irc_RPL_WHOISCHANNELS(self,prefix,params):
        ircname=params[1]
        foo=[]
        for i in string.split(params[2]," "):
            if i:
                while i[0] in ['@','+']:
                    i=i[1:]
                foo.append(i)
        self.receiveDirectMessage("**irc**","%s is on %s" % (ircname,
                                                string.join(foo,",")))


def sendAction(im,gateway,group,currenttext,currentusers):
    return "\001ACTION %s\001"%currenttext

def setNick(im,gateway,group,currenttext,currentusers):
    gateway.setNick(currenttext)
    return ""

def sendIM(im,gateway,group,text,users):
    for u in users:
        im.conversationWith(gateway,u)
    return text

def whoisUser(im,gateway,group,text,users):
    for u in users:
        gateway.sendLine("WHOIS %s"%u)
    return text

groupExtras=[
    ["Send Action",sendAction],
    ["Set Nick",setNick],
    ["Send IM",sendIM],
    ["Whois",whoisUser]
]

conversationExtras=[]

contactListExtras=[]
