# -*- test-case-name: twisted.web2.test.test_httpauth -*-

from twisted.cred import credentials, error
from twisted.web2.auth.interfaces import ICredentialFactory

from zope.interface import implements

class BasicCredentialFactory(object):
    """
    Credential Factory for HTTP Basic Authentication
    """

    implements(ICredentialFactory)

    scheme = 'basic'

    def __init__(self, realm):
        self.realm = realm

    def getChallenge(self, peer):
        return {'realm': self.realm}

    def decode(self, response, request):
        try:
            creds = (response + '===').decode('base64')
        except:
            raise error.LoginFailed('Invalid credentials')

        creds = creds.split(':', 1)
        if len(creds) == 2:
            return credentials.UsernamePassword(*creds)
        else:
            raise error.LoginFailed('Invalid credentials')
