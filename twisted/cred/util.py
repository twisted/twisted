
# System Imports
import md5
import random


class Unauthorized(Exception):
    """An exception that is raised when unauthorized actions are attempted.
    """


def respond(challenge, password):
    """Respond to a challenge.
    This is useful for challenge/response authentication.
    """
    m = md5.new()
    m.update(password)
    hashedPassword = m.digest()
    m = md5.new()
    m.update(hashedPassword)
    m.update(challenge)
    doubleHashedPassword = m.digest()
    return doubleHashedPassword

def challenge():
    """I return some random data.
    """
    crap = ''
    for x in range(random.randrange(15,25)):
        crap = crap + chr(random.randint(65,90))
    crap = md5.new(crap).digest()
    return crap
