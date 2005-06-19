import warnings
warnings.warn("twisted.conch.credentials is deprecated, use twisted.cred.credentials", DeprecationWarning, stackLevel=3)

from twisted.cred import credentials
IUsernamePassword = credentials.IUsernamePassword
UsernamePassword = credentials.UsernamePassword
ISSHPrivateKey = credentials.ISSHPrivateKey
SSHPrivateKey = credentials.SSHPrivateKey
IPluggableAuthenticationModules = credentials.IPluggableAuthenticationModules
PluggableAuthenticationModules = credentials.PluggableAuthenticationModules
