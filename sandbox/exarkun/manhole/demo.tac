
from twisted.application import service
application = service.Application("TAC Demo")

from twisted.cred import checkers
from tap import makeService
chk = checkers.InMemoryUsernamePasswordDatabaseDontUse(username="password")
makeService({"telnetPort": "tcp:6023",
             "sshPort": "tcp:6022",
             "namespace": {"foo": "bar"},
             "checkers": [chk]}).setServiceParent(application)
