import quoteproto
import quoters
from twisted.python import usage
class Options(usage.Options):
    optParameters = [["port", "p", 8007,
                      "Port number to listen on for QOTD protocol."],
                     ["static", "s", "An apple a day keeps the doctor away.",
                      "A static quote to display."],
                     ["file", "f", None,
                      "A fortune-format text file to read quotes from."]]

def updateApplication(app, config):
    port = int(config["port"])
    if config["file"]:
        quoter = quoters.FortuneQuoter([config['file']])
    else:
        quoter = quoters.StaticQuoter(config['static'])
    app.listenTCP(port, quoteproto.QOTDFactory(quoter))
