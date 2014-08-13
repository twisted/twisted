# -*- test-case-name: twisted.conch.test.test_ckeygen -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implementation module for the `ckeygen` command.
"""

import sys, os, getpass, socket
if getpass.getpass == getpass.unix_getpass:
    try:
        import termios # hack around broken termios
        termios.tcgetattr, termios.tcsetattr
    except (ImportError, AttributeError):
        sys.modules['termios'] = None
        reload(getpass)

from twisted.conch.ssh import keys
from twisted.python import failure, filepath, log, usage, randbytes



class GeneralOptions(usage.Options):
    synopsis = """Usage:    ckeygen [options]
 """

    longdesc = "ckeygen manipulates public/private keys in various ways."

    optParameters = [['bits', 'b', 1024, 'Number of bits in the key to create.'],
                     ['filename', 'f', None, 'Filename of the key file.'],
                     ['type', 't', None, 'Specify type of key to create.'],
                     ['comment', 'C', None, 'Provide new comment.'],
                     ['newpass', 'N', None, 'Provide new passphrase.'],
                     ['pass', 'P', None, 'Provide old passphrase.']]

    optFlags = [['fingerprint', 'l', 'Show fingerprint of key file.'],
                ['changepass', 'p', 'Change passphrase of private key file.'],
                ['quiet', 'q', 'Quiet.'],
                ['no-passphrase', None, "Create the key with no passphrase."],
                ['showpub', 'y', 'Read private key file and print public key.']]

    compData = usage.Completions(
        optActions={"type": usage.CompleteList(["rsa", "dsa"])})

    _default_filename_fmt = '~/.ssh/id_{}'
    _raw_input = raw_input
    
    def postOptions(self):
        # all methods of this script need a default filename
        #  so it should be set *outside* single methods
        if self['type']:
            self['create'] = True
        else:
            self['create'] = False
            # for all methods, default option is 'rsa'
            self['type'] = 'rsa'
                 
        # A bit of validation
        if self['create'] and self['showpub']:
            raise ValueError("Please select only one option between -t and -y")   
        # Now that I've divided action and type, I can get 
        #  the right default filename
        if self['filename'] is None:
            default_filename = os.path.expanduser(self._default_filename_fmt.format(self['type']))
            if self['showpub']:
                default_filename += ".pub"
            filename = self._raw_input('Enter filename (Default: %s)' % (default_filename,)).strip()
            if not filename:
                filename = default_filename
            self['filename'] = filename




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

    if options['create']:
        # The rsa/dsa type is moved to Option.postOptions
        generateKey(options)
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
    global exitStatus
    exitStatus = 2
    log.err(failure.Failure())
    raise


def generateRSAkey(options):
    #from Crypto.PublicKey import RSA
    #print 'Generating public/private rsa key pair.'
    #key = RSA.generate(int(options['bits']), randbytes.secureRandom)
    #_saveKey(key, options)
    if options['type'] != 'rsa':
        raise ValueError("Expected rsa, got %r" % options['type'])
    return generateKey(options)

def generateDSAkey(options):    
    if options['type'] != 'dsa':
        raise ValueError("Expected dsa, got %r" % options['type'])
    return generateKey(options)

def generateKey(options):
    """Generate an encryption key after options['type']
    """
    from Crypto.PublicKey import DSA, RSA
    kmap = {'rsa':RSA.generate, 'dsa': DSA.generate} # dispatch table
    allowed_values = kmap.keys()
    if not options['type'] in allowed_values:
        sys.exit('Key type was %s, must be one of: %s' % (options['type'], allowed_values))
        
    print 'Generating public/private %s key pair.' % options['type']
    generateKey = kmap[options['type']]
    key = generateKey(int(options['bits']), randbytes.secureRandom)
    _saveKey(key, options)


def printFingerprint(options):
    try:
        key = keys.Key.fromFile(options['filename'])
        obj = key.keyObject
        print '%s %s %s' % (
            obj.size() + 1,
            key.fingerprint(),
            os.path.basename(options['filename']))
    except:
        sys.exit('bad key')



def changePassPhrase(options):
    try:
        key = keys.Key.fromFile(options['filename']).keyObject
    except keys.EncryptedKeyError as e:
        # Raised if password not supplied for an encrypted key
        if not options.get('pass'):
            options['pass'] = getpass.getpass('Enter old passphrase: ')
        try:
            key = keys.Key.fromFile(
                options['filename'], passphrase=options['pass']).keyObject
        except keys.BadKeyError:
            sys.exit('Could not change passphrase: old passphrase error')
        except keys.EncryptedKeyError as e:
            sys.exit('Could not change passphrase: %s' % (e,))
    except keys.BadKeyError as e:
        sys.exit('Could not change passphrase: %s' % (e,))

    if not options.get('newpass'):
        while 1:
            p1 = getpass.getpass(
                'Enter new passphrase (empty for no passphrase): ')
            p2 = getpass.getpass('Enter same passphrase again: ')
            if p1 == p2:
                break
            print 'Passphrases do not match.  Try again.'
        options['newpass'] = p1

    try:
        newkeydata = keys.Key(key).toString('openssh',
                                            extra=options['newpass'])
    except Exception as e:
        sys.exit('Could not change passphrase: %s' % (e,))

    try:
        keys.Key.fromString(newkeydata, passphrase=options['newpass'])
    except (keys.EncryptedKeyError, keys.BadKeyError) as e:
        sys.exit('Could not change passphrase: %s' % (e,))

    fd = open(options['filename'], 'w')
    fd.write(newkeydata)
    fd.close()

    print 'Your identification has been saved with the new passphrase.'



def displayPublicKey(options): 
    try:
        key = keys.Key.fromFile(options['filename']).keyObject
    except keys.EncryptedKeyError:
        if not options.get('pass'):
            options['pass'] = getpass.getpass('Enter passphrase: ')
        key = keys.Key.fromFile(
            options['filename'], passphrase = options['pass']).keyObject
    print keys.Key(key).public().toString('openssh')



def _saveKey(key, options):
    # a bit of thesting
    kind = keys.objectType(key)
    kind = {'ssh-rsa':'rsa','ssh-dss':'dsa'}[kind]
    if not kind == options['type']:
        raise ValueError("Mismatch between key type (%s) and the passed one (%s)" % (kind, options['type']))
    
    if os.path.exists(options['filename']):
        print '%s already exists.' % options['filename']
        yn = raw_input('Overwrite (y/n)? ')
        if yn[0].lower() != 'y':
            sys.exit()
    if options.get('no-passphrase'):
        options['pass'] = b''
    elif not options['pass']:
        while 1:
            p1 = getpass.getpass('Enter passphrase (empty for no passphrase): ')
            p2 = getpass.getpass('Enter same passphrase again: ')
            if p1 == p2:
                break
            print 'Passphrases do not match.  Try again.'
        options['pass'] = p1

    keyObj = keys.Key(key)
    comment = '%s@%s' % (getpass.getuser(), socket.gethostname())

    filepath.FilePath(options['filename']).setContent(
        keyObj.toString('openssh', options['pass']))
    os.chmod(options['filename'], 33152)

    filepath.FilePath(options['filename'] + '.pub').setContent(
        keyObj.public().toString('openssh', comment))

    print 'Your identification has been saved in %s' % options['filename']
    print 'Your public key has been saved in %s.pub' % options['filename']
    print 'The key fingerprint is:'
    print keyObj.fingerprint()



if __name__ == '__main__':
    run()
