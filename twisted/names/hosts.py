
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
import string

def searchFileFor(file, name):
    fp = open(file)
    lines = fp.readlines()
    for line in lines:
        idx = string.find(line, '#')
        if idx:
            line = line[:idx]
        if not line:
            continue
        parts = string.split(line)
        if len(parts) != 3:
            continue
        if parts[2] == name:
            return parts[0]
        return None

class Resolver:

    def __init__(self, file='/etc/hosts'):
        self.file = file

    def resolve(self, name, callback, errback=None, type=1, timeout=10):
        if type != 1:
            fail()
        res = searchFileFor(self.file, name)
        if res is not None:
            callback(res)
        else:
            errback()
