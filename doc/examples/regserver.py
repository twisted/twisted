from twisted.web.widgets import Form, Gadget, FORGET_IT
from twisted.enterprise.row import RowObject, DBReflector
from twisted.cred.util import challenge
import md5

class License(RowObject):
    rowColumns = [
        'license_key',
	'license_secret',
	'license_type',
	'license_user',
	'license_email',
	'license_org',
	'license_dir',
	'license_host',
        ]
    def __init__(self,
                 license_key,
                 license_secret,
                 license_type,
                 license_user,
                 license_email,
                 license_org,
                 license_dir,
                 license_host):
        self.assignKeyAttr('license_key', license_key)
        self.license_secret = license_secret
        self.license_type = license_type
        self.license_user = license_user
        self.license_email = license_email
        self.license_org = license_org
        self.license_dir = license_dir
        self.license_host = license_host
        

licenseTypes = {"adamantium": "Adamantium License (Developer)",
                "mithril": "Mithril License (Personal)",
                "dilithium": "Dilithium License (Business)",
                "trilithium": "Trilithium License (Enterprise)"}

_ltypes = licenseTypes.items()
_ltypes.sort()

class RegServer(Form):
    formFields = [
        ['string', 'Administrator Name', 'license_user', '',
         'Your Name.'],
        ['string', 'Organization Name', 'license_org', '',
         'The name of the organization to create the license for.'],
        ['string', 'Email Address', 'license_email', '',
         'Enter an e-mail address here if you want us to contact you.'],
        ['menu', 'License Type', 'license_type', _ltypes,
         'Enter the type of license you desire.'],
        ['string', 'License Host', 'license_host', '',
         'The hostname that you will be using this server on.'],
        ['string', 'Working Directory', 'license_dir', '',
         'The directory on your host where Twisted will be run.',
        ]]
    title = "Twisted Daemon Registration Form"
    actionURI='twisted-registration'
    
    def __init__(self, dbpool):
        # Form.__init__(self)
        self.reflector = DBReflector(dbpool,
                                     [(License, "licenses",
                                       [("license_key", "varchar")])],
                                     self.populated)

    def populated(self, ignored):
        print 'regserver populated!!'
        
    keyfile = "KEYFILE"
    
    def process(self,
                write,
                request,
                submit,
                license_type,
                license_user,
                license_email,
                license_org,
                license_dir,
                license_host
                ):
        # Yay for single-threadedness.
        kf = open(self.keyfile).read()
        k = int(kf)
        f = open(self.keyfile, 'w')
        f.write(str(k + 1))
        f.close()
        license_key = kf
        license_secret = md5.md5(challenge()).hexdigest()
        self.reflector.insertRow(License(
            license_key,
            license_secret,
            license_type,
            license_user,
            license_email,
            license_org,
            license_dir,
            license_host
            )).arm()
        request.setHeader("content-type", "text/x-twisted-license")
        request.write("""
# Twisted Registration File

# This is a site license file for a Twisted Server.  It contains a globally
# unique identifier and is intended to be used for one and only one persistent
# Twisted process at a time.  New license keys may be obtained at

# 	http://twistedmatrix.com/license

# While this license file was originally designed for twistd, it can be used
# with other Twisted servers and clients that require a registration file as
# well.  Simply drop it into the directory where you will be running that
# application, with the name 'twisted-registration' (no extension).

# A unique identifier for this license key.
LICENSE_KEY = %r
# A secret key, associated with the license in a database.
LICENSE_SECRET = %r
# The type of license that you have registered for.
LICENSE_TYPE = %r
# A central point of contact for this license.
LICENSE_USER = %r
LICENSE_EMAIL = %r
# The organization that this server was licensed to.
LICENSE_ORG = %r
# The directory that this license applies to.
LICENSE_DIR = %r
# The host name that this license applies to.
LICENSE_HOST = %r

""" % (
    license_key,
    license_secret,
    licenseTypes.get(license_type) or license_type,
    license_user,
    license_email,
    license_org,
    license_dir,
    license_host
    ))
        request.finish()
        return [FORGET_IT]
