# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

#
from twisted.conch.ssh.transport import SSHClientTransport, SSHCiphers
from twisted.python import usage

import sys

class ConchOptions(usage.Options):

    optParameters = [['user', 'l', None, 'Log in using this user name.'],
                     ['identity', 'i', None],
                     ['ciphers', 'c', None],
                     ['macs', 'm', None],
                     ['port', 'p', None, 'Connect to this port.  Server must be on the same port.'],
                     ['option', 'o', None, 'Ignored OpenSSH options'],
                     ['host-key-algorithms', '', None],
                     ['known-hosts', '', None, 'File to check for host keys'],
                     ['user-authentications', '', None, 'Types of user authentications to use.'],
                     ['logfile', '', None, 'File to log to, or - for stdout'],
                   ]

    optFlags = [['version', 'V', 'Display version number only.'],
                ['compress', 'C', 'Enable compression.'],
                ['log', 'v', 'Enable logging (defaults to stderr)'],
                ['nox11', 'x', 'Disable X11 connection forwarding (default)'],
                ['agent', 'A', 'Enable authentication agent forwarding'],
                ['noagent', 'a', 'Disable authentication agent forwarding (default)'],
                ['reconnect', 'r', 'Reconnect to the server if the connection is lost.'],
               ]
    zsh_altArgDescr = {"connection-usage":"Connection types to use"}
    #zsh_multiUse = ["foo", "bar"]
    zsh_mutuallyExclusive = [("agent", "noagent")]
    zsh_actions = {"user":"_users",
                   "ciphers":"_values -s , 'ciphers to choose from' %s" %
                       " ".join(SSHCiphers.cipherMap.keys()),
                   "macs":"_values -s , 'macs to choose from' %s" %
                       " ".join(SSHCiphers.macMap.keys()),
                   "host-key-algorithms":"_values -s , 'host key algorithms to choose from' %s" %
                       " ".join(SSHClientTransport.supportedPublicKeys),
                   #"user-authentications":"_values -s , 'user authentication types to choose from' %s" %
                   #    " ".join(???),
                   }
    #zsh_actionDescr = {"logfile":"log file name", "random":"random seed"}
    # user, host, or user@host completion similar to zsh's ssh completion
    zsh_extras = ['1:host | user@host:{_ssh;if compset -P "*@"; then _wanted hosts expl "remote host name" _ssh_hosts && ret=0 elif compset -S "@*"; then _wanted users expl "login name" _ssh_users -S "" && ret=0 else if (( $+opt_args[-l] )); then tmp=() else tmp=( "users:login name:_ssh_users -qS@" ) fi; _alternative "hosts:remote host name:_ssh_hosts" "$tmp[@]" && ret=0 fi}']

    def __init__(self, *args, **kw):
        usage.Options.__init__(self, *args, **kw)
        self.identitys = [] 
        self.conns = None

    def opt_identity(self, i):
        """Identity for public-key authentication"""
        self.identitys.append(i)

    def opt_ciphers(self, ciphers):
        "Select encryption algorithms"
        ciphers = ciphers.split(',')
        for cipher in ciphers:
            if not SSHCiphers.cipherMap.has_key(cipher):
                sys.exit("Unknown cipher type '%s'" % cipher)
        self['ciphers'] = ciphers


    def opt_macs(self, macs):
        "Specify MAC algorithms"
        macs = macs.split(',')
        for mac in macs:
            if not SSHCiphers.macMap.has_key(mac):
                sys.exit("Unknown mac type '%s'" % mac)
        self['macs'] = macs

    def opt_host_key_algorithms(self, hkas):
        "Select host key algorithms"
        hkas = hkas.split(',')
        for hka in hkas:
            if hka not in SSHClientTransport.supportedPublicKeys:
                sys.exit("Unknown host key type '%s'" % hka)
        self['host-key-algorithms'] = hkas

    def opt_user_authentications(self, uas):
        "Choose how to authenticate to the remote server"
        self['user-authentications'] = uas.split(',')

#    def opt_compress(self):
#        "Enable compression"
#        self.enableCompression = 1
#        SSHClientTransport.supportedCompressions[0:1] = ['zlib']
