import sha
import md5
import hmac
import time

def P_hash(hash, secret, seed, bytes):
    """Data expansion function.
    
    @type secret: C{str}
    @type seed: C{str}
    @type bytes: C{int}
    @rtype: C{str}
    """
    def A(i):
        if i == 0:
            return seed
        return hmac.hmac(secret, A(i - 1), hash).digest()
    n = 0
    r = ''
    while len(r) < bytes:
        n += 1
        r += hmac.hmac(secret, A(n) + seed, hash).digest()
    return r[:bytes]

def P_MD5(secret, seed, bytes):
    return P_hash(md5, secret, seed, bytes)

def P_SHA1(secret, seed, bytes):
    return P_hash(sha, secret, seed, bytes)

def dividedSecret(secret):
    """Divide a secret into two equal-length portions.
    
    @type secret: C{str}
    @rtype: 2 C{tuple} of C{str}
    """
    half = math.ceil(len(secret) / 2.0)
    if half % 2 == 0:
        return secret[:half], secret[half:]
    return secret[:half], secret[half-1:]

def XOR(A, B):
    return ''.join([chr(ord(a) ^ ord(b)) for (a, b) in zip(A, B)])

def PRF(secret, label, seed):
    S1, S2 = dividedSecret(secret)
    return XOR(P_MD5(S1, label + seed), P_SHA1(S2, label + seed))

def HMAC_hash(hash, writeSecret, seqNum, type, version, fragment):
    # seqNum is 64 bits
    assert seqNum < (2 ** 64)
    seqNum = struct.pack('>II', seqNum >> 32, seqNum & 0xffffffff)
    version = struct.pack('>BB', *version)
    length = struct.pack('>H', len(fragment))
    return hmac.hmac(writeSecret, seqNum + chr(contentType) + version + length + fragment, hash).digest()

def HMAC_MD5(writeSecret, seqNum, type, version, fragment):
    return HMAC_hash(md5, writeSecret, seqNum, type, version, fragment)
def HMAC_SHA(writeSecret, seqNum, type, version, fragment):
    return HMAC_hash(sha, wrietSecret, seqNum, type, version, fragment)
def HMAC_NULL(writeSecret, seqNum, type, version, fragment):
    return ""

def getRandomBytes(n):
    s = "\xde\xad\xbe\xef"
    s = s * (n / len(s) + 1)
    return s[:n]
