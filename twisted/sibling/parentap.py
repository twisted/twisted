
from twisted.python import usage
from twisted.spread import pb
from twisted.sibling.parentserv import MotherService

class Options(usage.Options):
    optParameters = [
        ["port", "p", 7879, "Port number to listen on."],
        ["secret", "s", "qux", "Shared Secret"],
        ["service", "", "twisted.sibling.parent", "Service Name of Mother"]
        ]

def updateApplication(app, config):
    app.addService(MotherService(config['secret'], config['service'], app))
    app.listenTCP(config['port'], pb.BrokerFactory(pb.AuthRoot(app)))
