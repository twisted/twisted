"""
Entry point to invoke 'twistd' functionality using
'python -m twisted.twistd'
"""

from twisted.scripts import twistd

if __name__ == '__main__':
    twistd.run()
