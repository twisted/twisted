import os, time, cPickle

class DomainPickler:

    def __init__(self, path):
        self.path = path
        self.n = 0

    def exists(self, user, domain):
        return 1

    def saveMessage(self, origin, name, message, domain):
        fname = "%s_%s_%s" % (os.getpid(), os.time(), self.n)
        self.n = self.n+1
        fp = open(os.path.join(self.path, fname), 'w')
        try:
            cPickle.dump((origin, '%s@%s' % (name, domain), message), fp)
        finally:
            fp.close()
