
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
I am the support module for making a ftp server with mktap.
"""

from twisted.protocols import ftp
from twisted.python import usage
from twisted.application import internet
from twisted.cred import error, portal, checkers, credentials

import os.path


class Options(usage.Options):
    synopsis = """Usage: mktap ftp [options].
    WARNING: This FTP server is probably INSECURE do not use it.
    """
    optParameters = [
        ["port", "p", "2121",                 "set the port number"],
        ["root", "r", "/usr/local/ftp",       "define the root of the ftp-site."],
        ["userAnonymous", "", "anonymous",    "Name of the anonymous user."]
    ]

    longdesc = ''


#def addUser(factory, username, password):
#    factory.userdict[username] = {}
#    if factory.otp:
#        from twisted.python import otp
#        factory.userdict[username]["otp"] = otp.OTP(password, hash=otp.md5)
#    else:
#        factory.userdict[username]["passwd"] = password

def makeService(config):
    f = ftp.FTPFactory()

    r = ftp.FTPRealm()
    r.tld = config['root']
    p = portal.Portal(r)
    p.registerChecker(checkers.AllowAnonymousAccess(), credentials.IAnonymous)

    f.tld = config['root']
    f.userAnonymous = config['userAnonymous']
    f.portal = p
    f.protocol = ftp.FTP
    
    try:
        portno = int(config['port'])
    except KeyError:
        portno = 2121
    return internet.TCPServer(portno, f)
