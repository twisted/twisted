
from irc2 import AdvancedClient

from twisted.python import failure
from twisted.python import log
import sys
log.startLogging(sys.stdout)

channels = ['#python', '#python2']

states = dict.fromkeys(channels)

class State(object):
    def __init__(self):
        self.voicedUsers = []

class Client(AdvancedClient):
    nickname = 'irc2test'
    lineRate = 0.9

    def signedOn(self):
        map(self.join, channels)

    def joined(self, channel):
        channel = channel.lower()
        self.names(channel).addCallback(self._cbJ, channel).addErrback(self._ebJ, channel)

    def _cbJ(self, names, channel):
        states[channel] = State()
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
            states[channel].voicedUsers.append(user)
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

from twisted.internet import reactor, protocol

def main():
    proto = Client()
    cf = protocol.ClientFactory()
    cf.protocol = lambda: proto
    reactor.connectTCP('irc.freenode.net', 6667, cf)
    return proto
