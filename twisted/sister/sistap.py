
from twisted.python import usage
from twisted.spread import pb
from twisted.sister.sisterserv import SisterService

class Options(usage.Options):
    optParameters = [
        ["port", "p", 7878, "Port number to listen on."],
        ["parent_host", "a", "localhost", "Hostname of Parent server."],
        ["parent_port", "r", 7879, "Port number of Parent server."],
        ["parent_service", "", "twisted.sister.parent",
         "Service name of Parent service."],
        ["secret", "s", "qux", "Shared secret."],
        ]

def updateApplication(app, config):
    s = SisterService(config['parent_host'], int(config['parent_port']),
                      config['parent_service'], int(config['port']),
                      config['secret'], application=app)
    app.addService(s)
    app.listenTCP(int(config['port']), pb.BrokerFactory(pb.AuthRoot(app)))
