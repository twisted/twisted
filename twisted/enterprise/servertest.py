# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

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

