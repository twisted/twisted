
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


"""
twisted.geometry: support module for twisted.reality map-editors which
want to lay out rooms on a 2d grid.

"""

#TR imports
import thing

X=0
Y=1

X1=0
Y1=1
X2=2
Y2=3

class Coords:
    def __init__(self, l):
        self.l = l
    def __getitem__(self, item):
        y=item / self.l.xdim
        x=item % self.l.xdim
        ret= (x,y,self.l.lists[x][y])
        return ret
        
class Grid:
    def __init__(self,xdim,ydim):
        self.xdim=xdim
        self.ydim=ydim
        self.lists=[]
        for i in xrange(ydim):
            self.lists.append([None]*ydim)
    def output(self):
        from sys import stdout
        from time import sleep
        print '---'
        for x, y, i in self.coords():
            if x == 0:
                print
            if i:
                stdout.write('*')
            else:
                stdout.write(' ')
            stdout.flush()
            # sleep(0.01)
        print
        print '---'

    def locate(self,item):
        x=0
        
        for l in self.lists:
            # put as much of this loop as possible into C
            try: return Point(x,l.index(item))
            except ValueError: pass
            x=x+1
            
        raise ValueError("Grid.locate(item): item not in grid")
    
    def setcoords(self):
        """
        super-naieve way of preserving geometry information.  This is
        a *BAD* idea ... it should be replaced with something better.
        """
        for x,y,i in self.coords():
            if i:
                i.geom_x=x
                i.geom_y=y
    
    def __getitem__(self, index):
        return self.lists[index]

    def expand(self,x,y):
        x=x-self.xdim
        y=y-self.ydim
        if x > 0:
            self.xinsert(self.xdim, x)
        if y > 0:
            self.yinsert(self.ydim, y)

        return (x > 0) or (y > 0)
    
    def xinsert(self, x, sz=1):
        for i in xrange(sz):
            self.lists.insert(x,[None]*self.ydim)
            self.xdim=self.xdim+1

    def yinsert(self, y, sz=1):
        for i in xrange(sz):
            map(lambda lst,y=y: lst.insert(y,None),
                self.lists)
            self.ydim=self.ydim+1

    def coords(self):
        return Coords(self)

class Point:
    def __init__(self,x,y):
        self.x=x
        self.y=y

    def __len__(self):
        return 2

    def __getitem__(self, item):
        if item == X: return self.x
        if item == Y: return self.y
        raise IndexError('points only have 2 numbers')

def midval(i,j):
    return (j+((i-j)/2))

def waypoint(x1,y1,x2,y2):
    return ( x1+((x2-x1)/5) ,
             y1+((y2-y1)/5) )

def midpoint(x1,y1,x2,y2):
    return ( x1+((x2-x1)/2),
             y1+((y2-y1)/2) )

def slope(x1,y1,x2,y2):
    m1=x1-x2
    m2=y1-y2
    if m2 == 0:
        return 'INF'
    return m1/m2

def linepoints(box1,box2):
    mpt=midpoint
    x1,y1 = apply(mpt,box1)
    x2,y2 = apply(mpt,box2)

    width=abs(box1[X1]-box1[X2])
    height=abs(box1[Y1]-box1[Y2])
    
    diffx=float(x1-x2) or 0.001
    diffy=float(y1-y2) or 0.001
    
    if abs(diffx) > abs(diffy):
        xq=cmp(diffx,0)*(width/2)
        yq=cmp(diffx,0)*(diffy/diffx)*(width/2)
    else:
        xq=cmp(diffy,0)*(diffx/diffy)*(height/2)
        yq=cmp(diffy,0)*(height/2)

    r=(x1+(xq*-1),y1+(yq*-1),
       x2+xq,y2+yq)
    return r


transdict = {
    "north":        Point( 0,-1),
    "northeast":    Point( 1,-1),
    "east":            Point( 1, 0),
    "southeast":    Point( 1, 1),
    "south":        Point( 0, 1),
    "southwest":    Point(-1, 1),
    "west":            Point(-1, 0),
    "northwest":    Point(-1, 1),
    "up":            Point( 5,-5),
    "down":            Point(-5, 5)
    }

revdict = {
    "north":"south",
    "northeast":"southwest",
    "east":"west",
    "southeast":"northwest",
    "south":"north",
    "southwest":"northeast",
    "west":"east",
    "northwest":"southeast",
    "down":"up",
    "up":"down",
    "in":"out",
    "out":"in"
    }

def reverse(direction):
    """reverse(compass direction string) -> opposite compass direction
    
    Returns the name of the compass direction opposite the one given;
    for example reverse('north') returns 'south'.
    """
    return revdict.get(direction, 'back')


def placed(room):
    return hasattr(room,'placed')

def place(room,grid,x,y,direction):
    if placed(room): return

    if x < 0:
        grid.xinsert(0, abs(x)); x=0
    if y < 0:
        grid.yinsert(0, abs(y)); y=0
        
    grid.expand(x+1, y+1)
    
    if grid[x][y]:
        if direction.x:
            if direction.x < 0:
                x=x+1
            grid.xinsert(x)
        if direction.y:
            if direction.y < 0:
                y=y+1
            grid.yinsert(y)
            
    room.placed=1
    
    grid[x][y]=room
    
    for name in room.exits:
        # exit=exit
        exit = room.findExit(name)
        if isinstance(exit,thing.Thing):
            pt=Point(5,5)
            try: pt=transdict[name]
            except: pass
            xy=grid.locate(room)
            
            place(exit,
                  grid,
                  xy.x+pt.x,
                  xy.y+pt.y,
                  pt)

def layout(reality):
    t=Grid(1,1)
    for room in reality.unplaced():
            place(room,t,0,0,transdict['down'])
    return t

def _test():
    from inherit import grounds
    from time import sleep
    l = layout(grounds.damien.root)
    # l.setcoords()
    l.output()

if __name__=='__main__':
    _test()
