
"""
A module for authentication.

This provides challenge/response authentication, a standardized exception for 

"""

import md5
import random
import time

class Unauthorized(Exception):
    """the Unauthorized exception
    
    This exception is raised when an action is not allowed, or a user is not
    authenticated properly.
    """

def challenge():
    """I return some random data.
    """
    crap = ''
    for x in range(random.randrange(15,25)):
        crap = crap + chr(random.randint(65,90))
    crap = md5.new(crap).digest()
    return crap

def respond(challenge, password):
    """Respond to a challenge.
    This is useful for challenge/response authentication.
    """
    m = md5.new(md5.new(password).digest())
    m.update(challenge)
    return m.digest()


class Authenticator:
    """A class which can authenticate users.
    """
    def __init__(self, userdict=None, encrypted=0):
        """Authenticator([userdict, encrypted])
        Initialize, taking 2 optional arguments; a dictionary mapping user
        names to passwords, and a flag indicating whether that list is already
        encrypted or not.
        """
        self.userdict=userdict or {'guest':'guest'}
        if self.userdict and not encrypted:
            for u,p in self.userdict.items():
                self.addUser(u,p)


    def addUser(self, user,password):
        """Add a user to this authenticator with a password.
        Add a user to me.  Their password will be stored as an MD5 hash, so
        it's safe to serialize (pickle, jelly, mencode) me to a file.
        """
        
        self.userdict[user] = md5.new(password).digest()

    def getPassword(self, username):
        """Get the encrypted for a username.
        I will return an MD5 hash of the password for a particular user.  If no
        password is found I will raise a KeyError.
        """
        return self.userdict[username]


    def check(self, user, plainpass):
        """Check the plaintext password of a given user.
        This will return the string `user' if it succeeds, otherwise it will
        raise Unauthorized().
        """

        try: pw = self.getPassword(user)
        except: pass
        else:
            if md5.new(plainpass).digest() == pw:
                return user
        raise Unauthorized()

    def getUser(self, username):
        """Get a representative user object.
        
        I will return an object representing the authenticated user for the
        given username.  (This is a guideline for subclasses; by default, this
        is the supplied username.)
        """
        return username
    
    def authenticate(self, user, challenge, passkey):
        """Attempt to authenticate a user.
        
        I take 3 arguments; a user, a challenge (some pseudorandom data,
        presumably previously issued from a call to self.challenge(user)), and
        a version of a password, hashed using the challenge.  If the user is
        valid and the passkey/challenge combination matches my stored one, then
        I will return an object representing the authenticated user.  (This is
        a guideline for subclasses; by default, this is the supplied username.)
        Otherwise, I will raise Unauthorized().

        I am useful for writing wire-protocols which wish to secure the user's
        password.
        """
        try:
            pw = self.getPassword(user)
        except:
            pass
        else:
            m = md5.new()
            m.update(pw)
            m.update(challenge)
            correct = m.digest()
            if passkey == correct:
                return self.getUser(user)
        raise Unauthorized()


