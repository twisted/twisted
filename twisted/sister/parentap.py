
from twisted.python import usage
from twisted.spread import pb
from twisted.sister.parentserv import ParentService

class Options(usage.Options):
    optParameters = [
        ["port", "p", 7879, "Port number to listen on."],
        ["secret", "s", "qux", "Shared Secret"],
        ["service", "", "twisted.sister.parent", "Service Name of Parent"]
        ]

def updateApplication(app, config):
    app.addService(ParentService(config['secret'], config['service'], app))
    app.listenTCP(config['port'], pb.BrokerFactory(pb.AuthRoot(app)))
