
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
Sometimes I have to do things differently just because I'm obnoxious.

This is an HTML 'templating engine' based on parentheses.  I'd like to say
's-expressions' or 'lists', but it's not, really.  Oh sure, it *uses* lists
internally, sometimes...

Anyway, such things are all the rage these days, so I figured I'd have to write
one.

LMX stands for the List Markup eXtension.
  
This is quite possibly the most awful code I've ever written in my life.
"""

import sys, types
from cStringIO import StringIO

# Useful Constants
K = 1

class LMX:
    template = '''
    (html,
    (head, (title,Hello World))
    (body,
    This is a demonstration of the LMX templating engine.
    (widget test)
    ))
    '''
    def __init__(self, template=None):
        if template is None:
            template = StringIO(self.template)
        self.parse(template)
        self.chew()

    def tag_widget(self, req, attrs, body):
        print (req, attrs, body)
        return 'hello world'

    def render(self):
        o = StringIO()
        #print self.chewed
        for item in self.chewed:
            if isinstance(item, types.StringType):
                o.write(item)
            else: #elif isinstance(item, types.TupleType):
                o.write(apply(getattr(self, "tag_"+item[0]), (o,)+item[1:]))
                
        return o.getvalue()

    def chomp(self, p, l):
        if isinstance(p, types.StringType):
            l[-1].write(p)
            return
        if len(p) == 1:
            func = getattr(self, "tag_%s"%p[0], None)
            if func:
                l[-1]=l[-1].getvalue()
                l.append(tuple(p))
                l.append(StringIO())
            else:
                l[-1].write("<%s>" % p[0])
        else:
            func = getattr(self, "tag_%s"%p[0], None)
            if func:
                l[-1]=l[-1].getvalue()
                l.append((p[0], p[1], p[2:]))
                l.append(StringIO())
            else:
                l[-1].write("<%s" % p[0])
                if p[1]:
                    l[-1].write(" ")
                    for ghh in p[1]:
                        self.chomp(ghh,l)
                l[-1].write(">")
                for i in p[2:]:
                    self.chomp(i, l)
                l[-1].write("</%s>" % (p[0]))
            
    def chew(self):
        l = [StringIO()]
        for p in self.parsed:
            self.chomp(p, l)
        l[-1]=l[-1].getvalue()
        self.chewed = l

    def parse(self, f):
        p = self._p(f.read, 0)
        self.parsed = p
        
    def _p(self, r, t=1):
        """This is the really heinous code.

        It's a state machine constructed entirely out of a giant 'if' tree.

        The idea for the syntax (in case this wreched implementation doesn't
        exactly jump off the page at you) is that expressions consist of
        (a[,b](...)).  In the section before the comma has a special rule -- if it
        finds a comma or a paren inside double quotes (""), they don't have any
        special meaning (this is so that <a href="...,..."> works properly).
        """
        m = [StringIO()]
        q = 0
        a = 0
        b = ' '        
        while 1:
            b = r(K)
            if t:
                if not b:
                    m[-1] = m[-1].getvalue()
                    return m
                if b == '\\':
                    b = r(K)
                    m[-1].write(b)
                    continue
                if b in (' ', '\n'):
                    t = 0
                    a = 1
                    m[-1] = m[-1].getvalue()
                    m.append([StringIO()]) 
                elif b == ',':
                    t = 0
                    a = 0
                    m[-1] = m[-1].getvalue()
                    m.append([])
                    m.append(StringIO())
                elif b == ')':
                    t = 0
                    a = 0
                    m[-1] = m[-1].getvalue()
                    return m
                else:
                    m[-1].write(b)
            elif q:
                if not b:
                    m[-1][-1] = m[-1][-1].getvalue()
                    return m
                if b == '\\':
                    b = r(K)
                    m[-1][-1].write(b)
                    continue
                m[-1][-1].write(b)
                if b == '"':
                    q = 0
            elif a:
                if not b:
                    m[-1][-1] = m[-1][-1].getvalue()
                    return m
                if b == '\\':
                    b = r(K)
                    m[-1][-1].write(b)
                    continue
                if b == ',':
                    a = 0
                    m[-1][-1] = m[-1][-1].getvalue()
                    m.append(StringIO())
                elif b == '(':
                    m[-1][-1] = m[-1][-1].getvalue()
                    m[-1].append(self._p(r))
                    m[-1].append(StringIO())
                elif b == ')':
                    a = 0
                    m[-1][-1] = m[-1][-1].getvalue()
                    m.append(StringIO())
                elif b == '"':
                    m[-1][-1].write(b)
                    q = 1
                else:
                    m[-1][-1].write(b)
            else:
                if not b:
                    m[-1] = m[-1].getvalue()
                    return m
                if b == '\\':
                    b = r(K)
                    m[-1].write(b)
                    continue
                if b == '(':
                    m[-1] = m[-1].getvalue()
                    m.append(self._p(r))
                    m.append(StringIO())
                elif b == ')':
                    m[-1] = m[-1].getvalue()
                    return m
                else:
                    m[-1].write(b)

#import pprint
#l = LMX()#open('page.lmx'))
# open("page.lmxhtml",'wb').write( l.asHtml())
#print l.chewed
#print l.render()
#pprint.pprint(l.parsed)
