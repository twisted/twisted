import sys
import distutils

from ntsvc import command

distutils.core.Distribution = command.TwistedAppDistribution

distutils.command.__all__.append('twistedservice')

sys.modules['distutils.command.twistedservice'] = command
