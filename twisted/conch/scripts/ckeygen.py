# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

#
# $Id: ckeygen.py,v 1.8 2003/05/10 14:03:40 spiv Exp $

#""" Implementation module for the `ckeygen` command.
#"""

from twisted.conch.ssh import keys
from twisted.python import log, usage, randbytes

import sys, os, getpass, md5, socket
if getpass.getpass == getpass.unix_getpass:
    try:
        import termios # hack around broken termios
        termios.tcgetattr, termios.tcsetattr
    except (ImportError, AttributeError):
        sys.modules['termios'] = None
        reload(getpass)

class GeneralOptions(usage.Options):
    synopsis = """Usage:    ckeygen [options]
 """

    optParameters = [['bits', 'b', 1024, 'Number of bits in the key to create.'],
                     ['filename', 'f', None, 'Filename of the key file.'],
                     ['type', 't', None, 'Specify type of key to create.'],
                     ['comment', 'C', None, 'Provide new comment.'],
                     ['newpass', 'N', None, 'Provide new passphrase.'],
                     ['pass', 'P', None, 'Provide old passphrase']]

    optFlags = [['fingerprint', 'l', 'Show fingerprint of key file.'],
                ['changepass', 'p', 'Change passphrase of private key file.'],
                ['quiet', 'q', 'Quiet.'],
                ['showpub', 'y', 'Read private key file and print public key.']]

    #zsh_altArgDescr = {"bits":"Number of bits in the key (default: 1024)"}
    #zsh_multiUse = ["foo", "bar"]
    #zsh_mutuallyExclusive = [("foo", "bar"), ("bar", "baz")]
    zsh_actions = {"type":"(rsa dsa)"}
    #zsh_actionDescr = {"logfile":"log file name", "random":"random seed"}

def run():
    options = GeneralOptions()
    try:
        options.parseOptions(sys.argv[1:])
    except usage.UsageError, u:
        print 'ERROR: %s' % u
        options.opt_help()
        sys.exit(1)
    log.discardLogs()
    log.deferr = handleError # HACK
    if options['type']:
        if options['type'] == 'rsa':
            generateRSAkey(options)
        elif options['type'] == 'dsa':
            generateDSAkey(options)
        else:
            sys.exit('Key type was %s, must be one of: rsa, dsa' % options['type'])
    elif options['fingerprint']:
        printFingerprint(options)
    elif options['changepass']:
        changePassPhrase(options)
    elif options['showpub']:
        displayPublicKey(options)
    else:
        options.opt_help()
        sys.exit(1)

def handleError():
    from twisted.python import failure
    global exitStatus
    exitStatus = 2
    log.err(failure.Failure())
    reactor.stop()
    raise

def generateRSAkey(options):
    from Crypto.PublicKey import RSA
    print 'Generating public/private rsa key pair.'
    key = RSA.generate(int(options['bits']), randbytes.secureRandom)
    _saveKey(key, options)

def generateDSAkey(options):
    from Crypto.PublicKey import DSA
    print 'Generating public/private dsa key pair.'
    key = DSA.generate(int(options['bits']), randbytes.secureRandom)
    _saveKey(key, options)

def printFingerprint(options):
    if not options['filename']:
        filename = os.path.expanduser('~/.ssh/id_rsa')
        options['filename'] = raw_input('Enter file in which the key is (%s): ' % filename)
    if os.path.exists(options['filename']+'.pub'):
        options['filename'] += '.pub'
    try:
        string = keys.getPublicKeyString(options['filename'])
        obj = keys.getPublicKeyObject(string)
        print '%s %s %s' % (
            obj.size()+1,
            ':'.join(['%02x' % ord(x) for x in md5.new(string).digest()]),
            os.path.basename(options['filename']))
    except:
        sys.exit('bad key')

def changePassPhrase(options):
    if not options['filename']:
        filename = os.path.expanduser('~/.ssh/id_rsa')
        options['filename'] = raw_input('Enter file in which the key is (%s): ' % filename)
    try:
        key = keys.getPrivateKeyObject(options['filename'])
    except keys.BadKeyError, e:
        if e.args[0] != 'encrypted key with no passphrase':
            raise
        else:
            if not options['pass']:
                options['pass'] = getpass.getpass('Enter old passphrase: ')
            key = keys.getPrivateKeyObject(options['filename'], passphrase = options['pass'])
    if not options['newpass']:
        while 1:
            p1 = getpass.getpass('Enter new passphrase (empty for no passphrase): ')
            p2 = getpass.getpass('Enter same passphrase again: ')
            if p1 == p2:
                break
            print 'Passphrases do not match.  Try again.'
        options['newpass'] = p1
    open(options['filename'], 'w').write(
    keys.makePrivateKeyString(key, passphrase=options['newpass']))
    print 'Your identification has been saved with the new passphrase.'

def displayPublicKey(options):
    if not options['filename']:
        filename = os.path.expanduser('~/.ssh/id_rsa')
        options['filename'] = raw_input('Enter file in which the key is (%s): ' % filename)
    try:
        key = keys.getPrivateKeyObject(options['filename'])
    except keys.BadKeyError, e:
        if e.args[0] != 'encrypted key with no passphrase':
            raise
        else:
            if not options['pass']:
                options['pass'] = getpass.getpass('Enter passphrase: ')
            key = keys.getPrivateKeyObject(options['filename'], passphrase = options['pass'])
    print keys.makePublicKeyString(key)

def _saveKey(key, options):
    if not options['filename']:
        kind = keys.objectType(key)
        kind = {'ssh-rsa':'rsa','ssh-dss':'dsa'}[kind]
        filename = os.path.expanduser('~/.ssh/id_%s'%kind)
        options['filename'] = raw_input('Enter file in which to save the key (%s): '%filename).strip() or filename
    if os.path.exists(options['filename']):
        print '%s already exists.' % options['filename']
        yn = raw_input('Overwrite (y/n)? ')
        if yn[0].lower() != 'y':
            sys.exit()
    if not options['pass']:
        while 1:
            p1 = getpass.getpass('Enter passphrase (empty for no passphrase): ')
            p2 = getpass.getpass('Enter same passphrase again: ')
            if p1 == p2:
                break
            print 'Passphrases do not match.  Try again.'
        options['pass'] = p1
    comment = '%s@%s' % (getpass.getuser(), socket.gethostname())
    open(options['filename'], 'w').write(
            keys.makePrivateKeyString(key, passphrase=options['pass']))
    os.chmod(options['filename'], 33152)
    open(options['filename']+'.pub', 'w').write(
            keys.makePublicKeyString(key, comment = comment))
    pubKey = keys.getPublicKeyString(data=keys.makePublicKeyString(key, comment=comment))
    print 'Your identification has been saved in %s' % options['filename']
    print 'Your public key has been saved in %s.pub' % options['filename']
    print 'The key fingerprint is:'
    print ':'.join(['%02x' % ord(x) for x in md5.new(pubKey).digest()])

if __name__ == '__main__':
    run()

