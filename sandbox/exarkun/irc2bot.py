
import time

from irc2 import AdvancedClient

from twisted.python import failure, log
from twisted.internet import defer, task

# import sys
# log.startLogging(sys.stdout)

metachannel = "#arnis"
channels = ['#arnis1', '#arnis2']

states = dict.fromkeys(channels)

class State(object):
    def __init__(self):
        self.voicedUsers = []

class Client(AdvancedClient):
    nickname = 'snuggle-bunny'
    lineRate = 0.9
    favoredChannel = ""
    def signedOn(self):
        self.msg("NickServ", "identify ")
        self.msg("ChanServ", "invite %s" % metachannel)
        self.join(metachannel)
        for ch in channels:
            d = self.join(ch)
            d.addCallback(Client.names, ch)
            d.addCallback(self._cbJ, ch)
            d.addErrback(self._ebJ, ch)

        
        self._cleanupRaceCall = task.LoopingCall(self._raceConditionsCanBeDefeated)
        self._cleanupRaceCall.start(10)
        
    def connectionLost(self, reason):
        self._cleanupRaceCall.stop()
        del self._cleanupRaceCall

    def _raceConditionsCanBeDefeated(self):
        allNames = []
        print 'Looking up names for', states.keys()
        self.names(*states.iterkeys()).addCallback(self._eliminateRaceResults)

    def _eliminateRaceResults(self, allNames):
        voicedUsers = {}
        unvoicedUsers = {}
        populations = []
        for (channel, nameListing) in allNames.iteritems():
            populations.append((len(nameListing), channel))
            for name in nameListing:
                if name.startswith('@'):
                    continue
                voice = False
                if name[:1] == '+':
                    voice = True
                    name = name[1:]
                if voice:
                    try:
                        del unvoicedUsers[name]
                    except KeyError:
                        pass
                    if name in voicedUsers:
                        self.mode(channel, False, 'v', user=name)
                    else:
                        voicedUsers[name] = True
                else:
                    unvoicedUsers.setdefault(name, []).append(channel)
        for user, channels in unvoicedUsers.iteritems():
            if user not in voicedUsers:
                self.mode(channels[0], True, 'v', user=user)
            
        populations.sort()
        print "Examining channel populations", populations
        print "Favored channel is", self.favoredChannel
        if (populations[1][0] -  populations[0][0]) > 1 and populations[0][1] != self.favoredChannel:            

            self.favoredChannel = populations[0][1]
            print "Setting new favored channel to", self.favoredChannel
            self.mode(metachannel, True, "f", mask=self.favoredChannel)
            

    def _cbJ(self, names, channel):
        state = states[channel] = State()
        state.voicedUsers.extend([nick[1:] for nick in names if nick[:1] == '+'])

    def _ebJ(self, failure, channel):
        print 'Failed to get names for', channel
        failure.printTraceback()

    def left(self, channel):
        channel = channel.lower()
        try:
            del states[channel]
        except KeyError:
            pass
        return AdvancedClient.left(self, channel)


    def userJoined(self, user, channel):
        user = user.lower()
        channel = channel.lower()
        for ch, st in states.iteritems():
            if user in st.voicedUsers:
                break
        else:
            state = states[channel]
            if state is not None:
                state.voicedUsers.append(user)
            self.mode(channel, True, 'v', user=user)

    def userLeft(self, user, channel):
        user = user.lower()
        channel = channel.lower()
        try:
            states[channel].voicedUsers.remove(user)
        except ValueError:
            pass

    def userQuit(self, user):
        user = user.lower()
        for st in states.itervalues():
            try:
                st.voicedUsers.remove(user)
            except ValueError:
                pass

    def userKicked(self, kickee, channel, kicker, message):
        self.userLeft(kickee, channel)

from twisted.internet import reactor, protocol

def main():
    proto = Client()
    cf = protocol.ClientFactory()
    cf.protocol = lambda: proto
    reactor.connectTCP('irc.freenode.net', 6667, cf)
    reactor.run()
    # return proto

main()

