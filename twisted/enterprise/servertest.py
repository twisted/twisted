from whrandom import randint
from twisted.internet import tcp, main
from twisted.python import delay
from twisted.spread import pb

import dbservice
import dbserver

import time

manager = dbserver.DbManager(
    service =  "sybase",
    server =   "max",
    database = "twisted",
    username = "twisted",
    password = "matrix",
    numConnections = 1 )


manager.addUser("sean", "test")
manager.addUser("glyph", "second")
for i in range(0,100):
    manager.addUser("trash", "xxx")
#manager.connect()
#time.sleep(3)
manager.disconnect()

service = dbservice.DbService(manager)

app = main.Application("db")

ticker = delay.Delayed()
ticker.ticktime = 1
ticker.loop(func=manager.update, args=(), ticks=0)

pbs = pb.BrokerFactory()
pbs.addService("db", service )
app.listenOn(8787, pbs)
app.addDelayed(ticker)
app.save()

