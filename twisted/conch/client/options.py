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
from twisted.conch.ssh.transport import SSHClientTransport
from twisted.python import usage

import sys

class ConchOptions(usage.Options):

    optParameters = [['user', 'l', None, 'Log in using this user name.'],
                     ['identity', 'i', None],
                     ['ciphers', 'c', None],
                     ['macs', 'm', None],
                     ['connection-usage', 'K', None],
                     ['port', 'p', None, 'Connect to this port.  Server must be on the same port.'],
                     ['option', 'o', None, 'Ignored OpenSSH options'],
                    ]

    optFlags = [['version', 'V', 'Display version number only.'],
                ['compress', 'C', 'Enable compression.'],
                ['log', 'v', 'Log to stderr'],
                ['nocache', 'I', 'Do not use an already existing connection if it exists.'],
                ['nox11', 'x', 'Disable X11 connection forwarding (default)'],
                ['agent', 'A', 'Enable authentication agent forwarding.'],
                ['noagent' 'a', 'Disable authentication agent forwarding (default.'],
               ]

    identitys = []
    conns = None

    def opt_identity(self, i):
        """Identity for public-key authentication"""
        self.identitys.append(i)

    def opt_ciphers(self, ciphers):
        "Select encryption algorithm"
        ciphers = ciphers.split(',')
        for cipher in ciphers:
            if cipher not in SSHClientTransport.supportedCiphers:
                sys.exit("Unknown cipher type '%s'" % cipher)
        self['ciphers'] = ciphers

    def opt_macs(self, macs):
        "Specify MAC algorithms"
        macs = macs.split(',')
        for mac in macs:
            if mac not in SSHClientTransport.supportedMACs:
                sys.exit("Unknown mac type '%s'" % mac)
        self['macs'] = macs

#    def opt_user_authentications(self, uas):
    def opt_connection_usage(self, conns):
        self.conns = conns.split(',')
        
#    def opt_compress(self):
#        "Enable compression"
#        self.enableCompression = 1
#        SSHClientTransport.supportedCompressions[0:1] = ['zlib']
