import string

from twisted.protocols import irc
from twisted.im.locals import GLADE_FILE, autoConnectMethods, ONLINE, openGlade
from twisted.im.chat import getContactsList, getGroup, getGroupConversation, getPerson, getConversation
from twisted.internet import tcp
from twisted.python.defer import succeed
      
class IRCPerson:
    def __init__(self,name,tocClient):
        self.name=name
        self.account=tocClient

    def isOnline(self):
        return ONLINE

    def getStatus(self):
        return "Online"

    def setStatus(self,status):
        self.status=status
        getContactsList().setContactStatus(self)

    def sendMessage(self, text, meta={}):
        if meta and meta.get("style", None) == "emote":
            self.account.ctcpMakeQuery(self.name,[('ACTION', text)])
            return succeed(text)
        self.account.msg(self.name,text)
        return succeed(text)

class IRCGroup:
    def __init__(self,name,tocClient):
        self.name=name
        self.account=tocClient

    def sendGroupMessage(self, text, meta={}):
        if meta and meta.get("style", None) == "emote":
            self.account.me(self.name,text)
            return succeed(text)
        self.account.say(self.name,text)
        return succeed(text)

    def leave(self):
        self.account.leave(self.name)
        self.account.getGroupConversation(self.name,1)
        
class IRCProto(irc.IRCClient):
    def __init__(self, account):
        self.account = account
        self._namreplies={}
        self._ingroups={}
        self._groups={}
        self._topics={}

    def getGroupConversation(self, name,hide=0):
        name=string.lower(name)
        return getGroupConversation(getGroup(name,self,IRCGroup),hide)

    def getPerson(self,name):
        return getPerson(name,self,IRCPerson)

    def connectionMade(self):
        if self.account.password:
            self.sendLine("PASS :%s" % account.password)
        self.setNick(self.account.nickname)
        self.sendLine("USER %s foo bar :GTK-IM user"%self.nickname)
        for channel in self.account.channels:
            self.joinGroup(channel)
        self.account.isOnline=1
        registerAccount(self)
        getContactsList()

    def setNick(self,nick):
        self.name=nick
        self.accountName="%s (IRC)"%nick
        irc.IRCClient.setNick(self,nick)

    def privmsg(self,username,channel,message):
        username=string.split(username,'!',1)[0]
        if username==self.name: return
        if channel[0]=='#':
            group=channel[1:]
            self.getGroupConversation(group).showGroupMessage(username, message)
            return
        getConversation(self.getPerson(username)).showMessage(message)

    def action(self,username,channel,emote):
        username=string.split(username,'!',1)[0]
        if username==self.name: return
        meta={'style':'emote'}
        if channel[0]=='#':
            group=channel[1:]
            self.getGroupConversation(group).showGroupMessage(username, emote, meta)
            return
        getConversation(self.getPerson(username)).showMessage(emote,meta)
    
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
    	self.getGroupConversation(group).setGroupMembers(self._namreplies[string.lower(group)])
    	del self._namreplies[string.lower(group)]

    def irc_RPL_TOPIC(self,prefix,params):
        self._topics[params[1][1:]]=params[2]

    def irc_333(self,prefix,params):
        group=params[1][1:]
        self.getGroupConversation(group).setTopic(self._topics[group],params[2])
        del self._topics[group]

    def irc_TOPIC(self,prefix,params):
        nickname=string.split(prefix,"!")[0]
        self.getGroupConversation(group).setTopic(params[2],nickname)

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
        for group in self._ingroups[nickname]:
            self.getGroupConversation(group).memberLeft(nickname)
        self._ingroups[nickname]=[]

    # GTKIM calls
    def joinGroup(self,name):
        self.join(name)
        self.getGroupConversation(name)

class IRCAccount:
    gatewayType = "IRC"
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
        self.isOnline = 0

    def __setstate__(self, d):
        self.__dict__ = d
        self.port = int(self.port)

    def __getstate__(self):
        self.isOnline = 0
        return self.__dict__

    def isOnline(self):
        return self.isOnline

    def logOn(self):
        tcp.Client(self.host, self.port, IRCProto(self))

class IRCAccountForm:
    def __init__(self, maanger):
        self.xml = openGlade(GLADE_FILE, root="IRCAccountWidget")
        self.widget = self.xml.get_widget("IRCAccountWidget")

    def create(self, accountName, autoLogin):
        return IRCAccount(
            accountName, autoLogin,
            self.xml.get_widget("ircNick").get_text(),
            self.xml.get_widget("ircPassword").get_text(),
            self.xml.get_widget("ircChannels").get_text(),
            self.xml.get_widget("ircServer").get_text(),
            int(self.xml.get_widget("ircPort").get_text()) )

from twisted.im.account import registerAccount
