
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
I am the support module for making a ftp server with twistd.
"""

from twisted.protocols import ftp
from twisted.python import usage
from twisted.application import internet
from twisted.cred import error, portal, checkers, credentials

import os.path


class Options(usage.Options):
    synopsis = """[options].
    WARNING: This FTP server is probably INSECURE do not use it.
    """
    optParameters = [
        ["port", "p", "2121",                 "set the port number"],
        ["root", "r", "/usr/local/ftp",       "define the root of the ftp-site."],
        ["userAnonymous", "", "anonymous",    "Name of the anonymous user."],
        ["password-file", "", None,           "username:password-style credentials database"],
    ]

    longdesc = ''


def makeService(config):
    f = ftp.FTPFactory()

    r = ftp.FTPRealm(config['root'])
    p = portal.Portal(r)
    p.registerChecker(checkers.AllowAnonymousAccess(), credentials.IAnonymous)

    if config['password-file'] is not None:
        p.registerChecker(checkers.FilePasswordDB(config['password-file'], cache=True))

    f.tld = config['root']
    f.userAnonymous = config['userAnonymous']
    f.portal = p
    f.protocol = ftp.FTP
    
    try:
        portno = int(config['port'])
    except KeyError:
        portno = 2121
    return internet.TCPServer(portno, f)
