# Note: this file assumes that Portal has been changed to cast to IRealm
# its first argument.
from twisted.python import components
from twisted.cred import portal

class IAvatar(components.Interface):
    def connect(self, mind, avatarId):
        """a mind has connected"
    def logout(self, mind, avatarId):
        """a mind has logged out"

class _NullAvatar:
    __implements__ = IAvatar
    def connect(self, mind, avatarId):
        pass
    def logout(self, mind, avatarId):
        pass
_nullAvatar = _NullAvatar()

class IAvatarFactory(components.Interface):
    def loadAvatar(self, avatarId):
        pass

class Realm(components.Adapter):
    __implements__ = portal.IRealm
    def requestAvatar(self, avatarId, mind, *interfaces):
        try:
            avatar = self.original(avatarId)
        except LookupError:
            raise NotImplementedError("object does not exist")
        for interface in interfaces:
            o = interface(avatar, None)
            if o is not None:
                break
        else:
            raise NotImplementedError("cannot follow specified interface")
        conn = IAvatar(avatar, _nullAvatar)
        conn.connect(mind, avatarId)
        return interface, o, lambda: conn.logout(mind, avatarId)

components.registerAdapter(Realm, IAvatarFactory, portal.IRealm)

class PersistentFactory:
    __implements__ = IAvatarFactory
    def __init__(self, original):
        self.original = original
        self.cache = {}
    def requestAvatar(self, avatarId):
        if avatarId in self.cache:
            return self.cache[avatarId]
        avatar = self.cache[avatarId] = self.original.requestAvatar(avatarId)
        return avatar

# Example: (based on doc/examples/cred.py)
# class AvatarFactory:
#     __implements__ = IAvatarFactory
# 
#     def requestAvatar(self, avatarId):
#         if avatarId == checkers.ANONYMOUS:
#             return AnonymousUser()
#         elif avatarId.isupper():
#             return  Administrator()
#         else:
#             return RegularUser()
# Use: portal.Portal(AvatarFactory())
#
# ------------------------------------------------------------------
# Example: (based on twisted/manhole/service.py)
# class ConnectedPerspective(components.Adapter):
#
#     __implements__ = IAvatar
#
#     def connect(self, mind, avatarId):
#         self.original.attached(mind, avatarId)
#
#     def logout(self, mind, avatarId):
#         self.original.detached(mind, avatarId)
#
# components.registerAdapter(ConnectedPerspective, Perspective, IAvatar)
#
# class AvatarFactory:
# 
#     __implements__ = IAvatarFactory
# 
#     def __init__(self, service):
#         self.service = service
# 
#     def requestAvatar(self, avatarId):
#         return Perspective(self.service)
#
# Use: portal.Portal(PersistentFactory(AvatarFactory(service)))
#
# -------------------------------------------------
# Example: (based on twisted/wev/woven/simpleguard.py)
# class MarkingFactory:
#
#    __implements__ = IAvatarFactory
#
#    def __init__(self, resource, nonauthenticated=None):
#        self.resource = resource
#        self.nonauthenticated = (nonauthenticated or
#                                 MarkAuthenticatedResource(resource, None))
#
#    def requestAvatar(self, avatarId):
#        if avatarId == checkers.ANONYMOUS:
#            return self.nonauthenticated
#        else:
#            return MarkAuthenticatedResource(self.resource, avatarId)
#
# Use: portal.Portal(MarkingFactory(resource, nonauthenticated))
#
# ----------------------------------------------
# Example: (based on doc/examples/pbecho.py)
#
# class SimpleFactory:
#    __implements__ = IAvatarFactory
#
#    def requestAvatar(self, avatarId):
#        return SimplePerpsective()
#
# Use: portal.Portal(SimpleFactory())
#
# ------------------------------------------------
# Example: (based on doc/examples/sshsimpleserver.py)
# 
# class SSHFactory:
#    __implements__ = IAvatarFactory
#    requestAvatar = SSHAvatar
#
# Use: portal.Portal(SSHFactory())
#
# ------------------------------------------------
# Example: (based on doc/examples/pbbenchserver.py)
#
# class SimpleFactory:
#     __implements__ = IAvatarFactory
#
#    def requestAvatar(self, avatarId):
#        p = PBBenchPerspective()
#        p.printCallPerSec()
#        return p
#
# Use: portal.Portal(SimpleFactory())
#
# ------------------------------------------------
# Example: (based on twisted/mail/maildir.py)
#
# class MaildirAvatars(components.Adapter):
#     __implements__ = IAvatarFactory
#
#    def requestAvatar(self, avatarId):
#         if avatarId == cred.checkers.ANONYMOUS:
#             return StringListMailbox([INTERNAL_ERROR])
#         else:
#             return MaildirMailbox(os.path.join(self.original.root, avatarId))
# components.registerAdapter(MaildirAvatars, MaildirDirdbmDomain,
#                                            IAvatarFactory)
#
# Use: portal.Portal(IAvatarFactory(MaildirDirdbmDomain(service, root,
#                                                       postmaster))
# Discussion: should Realm cast to IAvatarFactory?
#
# --------------------------------------------
# Example: (based on sandbox/glyph/dynademo/login.py
#
# class _LoggedInAvatar(AvatarAdapter):
#     def connect(self, mind, avatarId):
#         pass
#     def logout(self, mind, avatarId):
#         self.original.logout()
# components.registerAdapter(_LoggedInAvatar, LoggedIn, IAvatar)
# 
# class MyFactory:
#     __implements__ = IAvatarFactory
#     def requestAvatar(self, avatarId)
#         if avatarId:
#             return LoggedIn(avatarId)
#         else:
#             return BasePage()
#
# Use: portal.Portal(MyFactory())
