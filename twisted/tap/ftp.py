
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
import sys
import os.path


class Options(usage.Options):
    synopsis = """Usage: mktap ftp [options].
    WARNING: This FTP server currently is very simple and will
    not work with a number of clients. We are working on making
    it more interoperable."""
    optParameters = [["port", "p", "2121", "set the port number"],
                  ["root", "r", "/usr/local/ftp",
                   "define the root of the ftp-site."],
                  ["useranonymous", "", "anonymous"]]
    optFlags = [["anonymous", "a","allow anonymous logins"],
                ["thirdparty", "3", "allow third-party connections"],
                ["otp", "","activate One-Time Passwords"]]

    longdesc = ''


def addUser(factory, username, password):
    factory.userdict[username] = {}
    if factory.otp:
        from twisted.python import otp
        factory.userdict[username]["otp"] = otp.OTP(password, hash=otp.md5)
    else:
        factory.userdict[username]["passwd"] = password

def updateApplication(app, config):
    t = ftp.FTPFactory()
    # setting the config
    t.anonymous = config.opts['anonymous']
    t.thirdparty = config.opts['thirdparty']
    t.root = config.opts['root']
    t.useranonymous = config.opts['useranonymous']
    t.otp = config.opts['otp']
    t.userdict = {}

    # adding a default user
    addUser(t, "twisted", "twisted")

    try:
        portno = int(config.opts['port'])
    except KeyError:
        portno = 2121
    app.listenTCP(portno, t)
