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
import string

from twisted.protocols import irc
from twisted.im.locals import ONLINE
from twisted.internet import reactor
from twisted.internet.defer import succeed

import basesupport

class IRCPerson(basesupport.AbstractPerson):

    def imperson_whois(self):
        self.client.sendLine("WHOIS %s" % self.name)

    ### interface impl

    def isOnline(self):
        return ONLINE

    def getStatus(self):
        return "Online"

    def setStatus(self,status):
        self.status=status
        self.chat.getContactsList().setContactStatus(self)

    def sendMessage(self, text, meta={}):
        if meta and meta.get("style", None) == "emote":
            self.client.ctcpMakeQuery(self.name,[('ACTION', text)])
            return succeed(text)
        self.client.msg(self.name,text)
        return succeed(text)

class IRCGroup(basesupport.AbstractGroup):

    def imgroup_testAction(self):
        print 'action test!'

    def imtarget_kick(self, target):
        reason = "for great justice!"
        self.client.sendLine("KICK #%s %s :%s" % (
            self.name, target.name, reason))

    ### Interface Implementation
    
    def setTopic(self, topic):
        self.client.topic(self.name, topic)

    def sendGroupMessage(self, text, meta={}):
        if meta and meta.get("style", None) == "emote":
            self.client.me(self.name,text)
            return succeed(text)
        #standard shmandard, clients don't support plain escaped newlines!
        for line in string.split(text, '\n'): 
            self.client.say(self.name, line)
        return succeed(text)

    def leave(self):
        self.client.leave(self.name)
        self.client.getGroupConversation(self.name,1)

class IRCProto(basesupport.AbstractClientMixin, irc.IRCClient):
    def __init__(self, account, chatui):
        basesupport.AbstractClientMixin.__init__(self, account, chatui)
        self._namreplies={}
        self._ingroups={}
        self._groups={}
        self._topics={}

    def getGroupConversation(self, name,hide=0):
        name=string.lower(name)
        return self.chat.getGroupConversation(self.chat.getGroup(name,self,IRCGroup),hide)

    def getPerson(self,name):
        return self.chat.getPerson(name,self,IRCPerson)

    def connectionMade(self):
        try:
            print 'connection made on irc service!?', self
            if self.account.password:
                self.sendLine("PASS :%s" % self.account.password)
            self.setNick(self.account.nickname)
            self.sendLine("USER %s foo bar :GTK-IM user"%self.nickname)
            for channel in self.account.channels:
                self.joinGroup(channel)
            self.account._isOnline=1
            print 'uh, registering irc acct'
            self.registerAsAccountClient()
            self.chat.getContactsList()
        except:
            import traceback
            traceback.print_exc()

    def setNick(self,nick):
        self.name=nick
        self.accountName="%s (IRC)"%nick
        irc.IRCClient.setNick(self,nick)

    def kickedFrom(self, channel, kicker, message):
        """Called when I am kicked from a channel.
        """
        print 'ono i was kicked', channel, kicker, message
        return self.chat.getGroupConversation(
            self.chat.getGroup(channel[1:],self,IRCGroup),1)

    def userKicked(self, kickee, channel, kicker, message):
        print 'whew somebody else', kickee, channel, kicker, message


    def privmsg(self,username,channel,message):
        username=string.split(username,'!',1)[0]
        if username==self.name: return
        if channel[0]=='#':
            group=channel[1:]
            self.getGroupConversation(group).showGroupMessage(username, message)
            return
        self.chat.getConversation(self.getPerson(username)).showMessage(message)

    def action(self,username,channel,emote):
        username=string.split(username,'!',1)[0]
        if username==self.name: return
        meta={'style':'emote'}
        if channel[0]=='#':
            group=channel[1:]
            self.getGroupConversation(group).showGroupMessage(username, emote, meta)
            return
        self.chat.getConversation(self.getPerson(username)).showMessage(emote,meta)
    
    def irc_RPL_NAMREPLY(self,prefix,params):
        """
        RPL_NAMREPLY
        >> NAMES #bnl
        << :Arlington.VA.US.Undernet.Org 353 z3p = #bnl :pSwede Dan-- SkOyg AG
        """
        group=string.lower(params[2][1:])
        users=string.split(params[3])
        for ui in range(len(users)):
            while users[ui][0] in ["@","+"]: # channel modes
                users[ui]=users[ui][1:]
        if not self._namreplies.has_key(group):
            self._namreplies[group]=[]
        self._namreplies[group].extend(users)
        for nickname in users:
                try:
                    self._ingroups[nickname].append(group)
                except:
                    self._ingroups[nickname]=[group]

    def irc_RPL_ENDOFNAMES(self,prefix,params):
    	group=params[1][1:]
    	self.getGroupConversation(group).setGroupMembers(self._namreplies[string.lower(group)])
    	del self._namreplies[string.lower(group)]

    def irc_RPL_TOPIC(self,prefix,params):
        self._topics[params[1][1:]]=params[2]

    def irc_333(self,prefix,params):
        group=params[1][1:]
        self.getGroupConversation(group).setTopic(self._topics[group],params[2])
        del self._topics[group]

    def irc_TOPIC(self,prefix,params):
        nickname = string.split(prefix,"!")[0]
        group = params[0][1:]
        topic = params[1]
        self.getGroupConversation(group).setTopic(topic,nickname)

    def irc_JOIN(self,prefix,params):
        nickname=string.split(prefix,"!")[0]
        group=string.lower(params[0][1:])
        if nickname!=self.nickname:
            try:
                self._ingroups[nickname].append(group)
            except:
                self._ingroups[nickname]=[group]
            self.getGroupConversation(group).memberJoined(nickname)

    def irc_PART(self,prefix,params):
        nickname=string.split(prefix,"!")[0]
        group=string.lower(params[0][1:])
        if nickname!=self.nickname:
            if group in self._ingroups[nickname]:
                self._ingroups[nickname].remove(group)
                self.getGroupConversation(group).memberLeft(nickname)
            else:
                print "%s left %s, but wasn't in the room."%(nickname,group)

    def irc_QUIT(self,prefix,params):
        nickname=string.split(prefix,"!")[0]
        if self._ingroups.has_key(nickname):
            for group in self._ingroups[nickname]:
                self.getGroupConversation(group).memberLeft(nickname)
            self._ingroups[nickname]=[]
        else:
            print '*** WARNING: ingroups had no such key %s' % nickname

    def irc_NICK(self, prefix, params):
        fromNick = string.split(prefix, "!")[0]
        toNick = params[0]
        if not self._ingroups.has_key(fromNick):
            print "%s changed nick to %s. But she's not in any groups!?" % (fromNick, toNick)
            return
        for group in self._ingroups[fromNick]:
            self.getGroupConversation(group).memberChangedNick(fromNick, toNick)
        self._ingroups[toNick] = self._ingroups[fromNick]
        del self._ingroups[fromNick]

    def irc_unknown(self, prefix, command, params):
        print "unknown message from IRCserver. prefix: %s, command: %s, params: %s" % (prefix, command, params)

    # GTKIM calls
    def joinGroup(self,name):
        self.join(name)
        self.getGroupConversation(name)

class IRCAccount(basesupport.AbstractAccount):
    gatewayType = "IRC"
    _isOnline = 0
    def __init__(self, accountName, autoLogin, nickname, password, channels, host, port):
        self.accountName = accountName
        self.autoLogin = autoLogin
        self.nickname = nickname
        self.password = password
        self.channels=map(string.strip,string.split(channels,','))
        if self.channels==['']:
            self.channels=[]
        self.host = host
        self.port = port
        self._isOnline = 0

    def __setstate__(self, d):
        self.__dict__ = d
        self.port = int(self.port)

    def __getstate__(self):
        self._isOnline = 0
        return self.__dict__

    def isOnline(self):
        return self.isOnline

    def startLogOn(self, chatui):
        reactor.clientTCP(self.host, self.port, IRCProto(self, chatui))

