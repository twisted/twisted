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
import random
import time

from twisted.internet import tcp, main

import client


def getTestValue():
    value = int(time.time() * random.random())
    return value

c = client.MetricsClientComponent(7, "localhost", 8787)
c.doLogin("test", "sss")

c.createStateVariable("state", getTestValue, 10)
c.createCounterVariable("counter1", 3)
c.createCounterVariable("counter2", 4)
c.createCounterVariable("counter3", 5)

i = 0
while 1:
    main.iterate()
    i = i + 1
    if i % 5 == 0:
        ##
        r = random.random() * 40
        if r < 10:
            c.incrementCounterVariable("counter1")

        r = random.random() * 40
        if r < 20:
            c.incrementCounterVariable("counter2")

        r = random.random() * 40
        if r < 30:
            c.incrementCounterVariable("counter3")

    c.update()
    time.sleep(0.1)
