#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.words.protocols import oscar
from twisted.internet import protocol, reactor
import getpass

SN = raw_input('Username: ') # replace this with a screenname
PASS =  getpass.getpass('Password: ')# replace this with a password
if SN[0].isdigit():
    icqMode = 1
    hostport = ('login.icq.com', 5238)
else:
    hostport = ('login.oscar.aol.com', 5190)
    icqMode = 0

class B(oscar.BOSConnection):
    capabilities = [oscar.CAP_CHAT]
    def initDone(self):
        self.requestSelfInfo().addCallback(self.gotSelfInfo)
        self.requestSSI().addCallback(self.gotBuddyList)
    def gotSelfInfo(self, user):
        print user.__dict__
        self.name = user.name
    def gotBuddyList(self, l):
        print l
        self.activateSSI()
        self.setProfile("""this is a test of the current twisted.oscar code.<br>
current features:<br>
* send me a message, and you should get it back.<br>
* invite me to a chat room.  i'll repeat what people say.  say 'leave' and i'll go.<br>
* also, i hang out in '%s Chat'.  join that, i'll repeat what you say there.<br>
* try warning me.  just try it.<br>
<br>
if any of those features don't work, tell paul (Z3Penguin).  thanks."""%SN)
        self.setIdleTime(0)
        self.clientReady()
        self.createChat('%s Chat'%SN).addCallback(self.createdRoom)
    def createdRoom(self, (exchange, fullName, instance)):
        print 'created room',exchange, fullName, instance
        self.joinChat(exchange, fullName, instance).addCallback(self.chatJoined)
    def updateBuddy(self, user):
        print user
    def offlineBuddy(self, user):
        print 'offline', user.name
    def receiveMessage(self, user, multiparts, flags):
        print user.name, multiparts, flags
        self.getAway(user.name).addCallback(self.gotAway, user.name)
        if multiparts[0][0].find('away')!=-1:
            self.setAway('I am away from my computer right now.')
        elif multiparts[0][0].find('back')!=-1:
            self.setAway(None)
        if self.awayMessage:
            self.sendMessage(user.name,'<html><font color="#0000ff">'+self.awayMessage,autoResponse=1)
        else:
            self.lastUser = user.name
            self.sendMessage(user.name, multiparts, wantAck = 1, autoResponse = (self.awayMessage!=None)).addCallback( \
                self.messageAck)
    def messageAck(self, (username, message)):
        print 'message sent to %s acked' % username
    def gotAway(self, away, user):
        if away != None:
            print 'got away for',user,':',away
    def receiveWarning(self, newLevel, user):
        print 'got warning from', hasattr(user,'name') and user.name or None
        print 'new warning level', newLevel
        if not user:
            #username = self.lastUser
            return 
        else:
            username = user.name
        self.warnUser(username).addCallback(self.warnedUser, username)
    def warnedUser(self, oldLevel, newLevel, username):
        self.sendMessage(username,'muahaha :-p')
    def receiveChatInvite(self, user, message, exchange, fullName, instance, shortName, inviteTime):
            print 'chat invite from',user.name,'for room',shortName,'with message:',message
            self.joinChat(exchange, fullName, instance).addCallback(self.chatJoined)
    def chatJoined(self, chat):
        print 'joined chat room', chat.name
        print 'members:',map(lambda x:x.name,chat.members)
    def chatReceiveMessage(self, chat, user, message):
        print 'message to',chat.name,'from',user.name,':',message
        if user.name!=self.name: chat.sendMessage(user.name+': '+message)
        if message.find('leave')!=-1 and chat.name!='%s Chat'%SN: chat.leaveChat()
    def chatMemberJoined(self, chat, member):
        print member.name,'joined',chat.name
    def chatMemberLeft(self, chat, member):
        print member.name,'left',chat.name
        print 'current members',map(lambda x:x.name,chat.members)
        if chat.name!="%s Chat"%SN and len(chat.members)==1:
            print 'leaving', chat.name
            chat.leaveChat()

class OA(oscar.OscarAuthenticator):
   BOSClass = B

protocol.ClientCreator(reactor, OA, SN, PASS, icq=icqMode).connectTCP(*hostport)
reactor.run()
