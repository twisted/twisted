
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
Twisted Words UI Gateways: user-interface gateways for various services.
"""

# XXX: evil code to figure out and import all the gateways
import os
l=os.listdir(__path__[0])
g={}
for f in l:
    if f[:8]=="__init__":
        pass
    elif f[-3:]==".py" and not g.has_key(f[:-3]):
            g[f[:-3]]=__import__("twisted.words.ui.gateways."+f[:-3],{},{},["foo"])
    elif f[-4:]==".pyc" and not g.has_key(f[:-4]):
            g[f[:-4]]=__import__("twisted.words.ui.gateways."+f[:-4],{},{},["foo"])
__gateways__=g
