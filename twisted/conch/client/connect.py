# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2004 Matthew W. Lefkowitz
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
#
import direct, unix

connectTypes = {"direct" : direct.connect,
                "unix" : unix.connect}

def connect(host, port, options, verifyHostKey, userAuthObject):
    useConnects = options.conns or ['unix', 'direct']
    return _ebConnect(None, useConnects, host, port, options, verifyHostKey,
                      userAuthObject)

def _ebConnect(f, useConnects, host, port, options, vhk, uao):
    if not useConnects:
        return f
    connectType = useConnects.pop(0)
    f = connectTypes[connectType]
    d = f(host, port, options, vhk, uao)
    d.addErrback(_ebConnect, useConnects, host, port, options, vhk, uao)
    return d
