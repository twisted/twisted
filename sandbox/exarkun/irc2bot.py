
from irc2 import AdvancedClient

from twisted.python import failure, log
from twisted.internet import defer, task

import sys
log.startLogging(sys.stdout)

metachannel = ["#arnis"]
channels = ['#arnis1', '#arnis2']

states = dict.fromkeys(channels)

class State(object):
    def __init__(self):
        self.voicedUsers = []

class Client(AdvancedClient):
    nickname = 'irc2test'
    lineRate = 0.9

    def signedOn(self):
        map(self.join, channels)
        self._cleanupRaceCall = task.LoopingCall(self._raceConditionsCanBeDefeated)
        self._cleanupRaceCall.start(10)

    def connectionLost(self, reason):
        self._cleanupRaceCall.stop()
        del self._cleanupRaceCall

    def _raceConditionsCanBeDefeated(self):
        allNames = []
        for ch in states.iterkeys():
            allNames.append(self.names(ch).addCallback(lambda result, channel=ch: (channel, result)))
        defer.DeferredList(allNames).addCallback(self._eliminateRaceResults)

    def _eliminateRaceResults(self, allNames):
        voicedUsers = {}
        unvoicedUsers = {}
        for (channel, nameListing) in allNames:
            for name in nameListing:
                if name.startswith('+'):
                    try:
                        del unvoicedUsers[name[1:]]
                    except KeyError:
                        pass
                    if name in voicedUsers:
                        self.mode(channel, False, 'v', user=name)
                    else:
                        voicedUsers[name] = True
                else:
                    unvoicedUsers.setdefault(name, []).append(channel)
        for user, channels in unvoicedUsers.iteritems():
            self.mode(channels[0], True, 'v', user=user)

    def joined(self, channel):
        channel = channel.lower()
        self.names(channel).addCallback(self._cbJ, channel).addErrback(self._ebJ, channel)

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
    return proto
