
# System Imports
import string

# Twisted Imports
from twisted.words.service import WordsClient
from twisted.python.plugin import getPlugIns
from twisted.python.failure import Failure
from twisted.python import log

class BotBot(WordsClient):

    ## possibly generalizeable stuff

    def receiveDirectMessage(self, senderName, messageText, metadata=None):
        cmdline = string.split(messageText, ' ', 1)
        if len(cmdline) == 1:
            cmd, arg = cmdline[0], ''
        else:
            cmd, arg = cmdline
        try:
            getattr(self, "bot_%s" % cmd)(senderName, arg, metadata)
        except:
            f = Failure()
            self.voice.directMessage(senderName, f.getBriefTraceback())

    ### utility bot commands

    def bot_rebuild(self, sender, message, metadata):
        self.loadBotList()
        from twisted.words import botbot
        from twisted.python.rebuild import rebuild
        from twisted.python.reflect import namedModule
        if message:
            rebuild(namedModule(message))
        else:
            rebuild(botbot)

    def bot_blowup(self, sender, message, metadata):
        self.voice.directMessage(sender, "I am blowing up.")
        raise Exception("Kaboom!")

    ## setup stuff

    def setupBot(self, voice):
        self.voice = voice
        self.loadBotList()

    def loadBotList(self):
        botTypeList = getPlugIns("twisted.words.bot")
        botTypes = {}
        for bott in botTypeList:
            botTypes[bott.botType] = bott
        self.botTypes = botTypes

    ### botbot bot commands

    def bot_tlist(self, sender, message, metadata):
        self.voice.directMessage(sender,
                                 string.join(self.botTypes.keys(), " "))

    def bot_list(self, sender, message, metadata):
        self.voice.directMessage(sender, "Bot List")
        log.msg('starting bot list')
        import traceback
        try:
            for bot in self.voice.service.bots:
                self.voice.directMessage(sender, " - %s" % bot.voice.perspectiveName)
        except:
            traceback.print_exc(file=log.logfile)
        log.msg('finished bot list')
        self.voice.directMessage(sender, "End of Bot List")
        log.msg('finished')

    def bot_new(self, sender, message, metadata):
        bottype, botname = string.split(message, ' ', 1)
        self.voice.service.addBot(botname, self.botTypes[bottype].load().createBot())
        self.voice.directMessage(sender, "Bot Created!")

def createBot():
    return BotBot()
