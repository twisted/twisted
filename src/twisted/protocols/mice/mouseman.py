# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

#
"""Logictech MouseMan serial protocol.

http://www.softnco.demon.co.uk/SerialMouse.txt
"""

from twisted.internet import protocol

class MouseMan(protocol.Protocol):
    """

    Parser for Logitech MouseMan serial mouse protocol (compatible
    with Microsoft Serial Mouse).

    """

    state = 'initial'

    leftbutton=None
    rightbutton=None
    middlebutton=None

    leftold=None
    rightold=None
    middleold=None

    horiz=None
    vert=None
    horizold=None
    vertold=None

    def down_left(self):
        pass

    def up_left(self):
        pass

    def down_middle(self):
        pass

    def up_middle(self):
        pass

    def down_right(self):
        pass

    def up_right(self):
        pass

    def move(self, x, y):
        pass

    horiz=None
    vert=None

    def state_initial(self, byte):
        if byte & 1<<6:
            self.word1=byte
            self.leftbutton = byte & 1<<5
            self.rightbutton = byte & 1<<4
            return 'horiz'
        else:
            return 'initial'

    def state_horiz(self, byte):
        if byte & 1<<6:
            return self.state_initial(byte)
        else:
            x=(self.word1 & 0x03)<<6 | (byte & 0x3f)
            if x>=128:
                x=-256+x
            self.horiz = x
            return 'vert'

    def state_vert(self, byte):
        if byte & 1<<6:
            # short packet
            return self.state_initial(byte)
        else:
            x = (self.word1 & 0x0c)<<4 | (byte & 0x3f)
            if x>=128:
                x=-256+x
            self.vert = x
            self.snapshot()
            return 'maybemiddle'

    def state_maybemiddle(self, byte):
        if byte & 1<<6:
            self.snapshot()
            return self.state_initial(byte)
        else:
            self.middlebutton=byte & 1<<5
            self.snapshot()
            return 'initial'

    def snapshot(self):
        if self.leftbutton and not self.leftold:
            self.down_left()
            self.leftold=1
        if not self.leftbutton and self.leftold:
            self.up_left()
            self.leftold=0

        if self.middlebutton and not self.middleold:
            self.down_middle()
            self.middleold=1
        if not self.middlebutton and self.middleold:
            self.up_middle()
            self.middleold=0

        if self.rightbutton and not self.rightold:
            self.down_right()
            self.rightold=1
        if not self.rightbutton and self.rightold:
            self.up_right()
            self.rightold=0

        if self.horiz or self.vert:
            self.move(self.horiz, self.vert)

    def dataReceived(self, data):
        for c in data:
            byte = ord(c)
            self.state = getattr(self, 'state_'+self.state)(byte)
