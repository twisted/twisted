
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

import sys
import socket

LICENSE_KEY = ""                # An ID which is most likely globally unique.
LICENSE_TYPE = "Unregistered"   # The type of license the user has purchased.
LICENSE_USER = "Nobody"         # Name of the user who registered this server
LICENSE_EMAIL = ""              # Email Address of the registered user
LICENSE_ORG = "Yoyodyne, Inc"   # Institution that registered this server
LICENSE_HOST = socket.getfqdn() # Hostname for which this server registered
LICENSE_DIR = ""                # directory name the server should run from
LICENSE_SECRET = ""             # Trivial precaution against people stealing ID numbers

def checkLicenseFile():
    try:
        d = {}
        execfile("twisted-registration", d, d)
    except IOError:
        sys.stderr.write("""
NOTICE: This copy of Twisted is UNREGISTERED!  See doc/howto/register.html to
register your copy today!

If you believe the LICENSE file or the Twisted Matrix Labs software you have
received is not legally licensed and/or may be counterfeit, please e-mail
Twisted Matrix Labs at piracy@twistedmatrix.com.

""")
        sys.stderr.flush()
    else:
        try:
            global LICENSE_KEY, \
                   LICENSE_TYPE, \
                   LICENSE_USER, \
                   LICENSE_EMAIL, \
                   LICENSE_ORG, \
                   LICENSE_DIR, \
                   LICENSE_HOST, \
                   LICENSE_SECRET
            LICENSE_KEY = d['LICENSE_KEY']
            LICENSE_TYPE = d['LICENSE_TYPE']
            LICENSE_USER = d['LICENSE_USER']
            LICENSE_EMAIL = d['LICENSE_EMAIL']
            LICENSE_ORG = d['LICENSE_ORG']
            LICENSE_DIR = d['LICENSE_DIR']
            LICENSE_HOST = d['LICENSE_HOST']
            LICENSE_SECRET = d['LICENSE_SECRET']
        except:
            sys.stderr.write("""
WARNING: The license file is INVALID and MAY HAVE BEEN TAMPERED WITH!!  Alert
Twisted Matrix Labs at piracy@twistedmatrix.com (Please be sure to include your
Customer Service Number).

""")
