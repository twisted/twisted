from twisted.python import components
from twisted.cred import portal

class IAvatar(components.Interface):
    def connect(self, mind):
        """a mind has connected"
    def logout(self, mind):
        """a mind has logged out"

class _NullAvatar:
    __implements__ = IAvatar
    def connect(self, mind):
        pass
    def logout(self, mind):
        pass
_nullAvatar = _NullAvatar()

class AvatarAdapter(components.Adapter):
    __implements__ = IAvatar
    def connected(self, mind):
        pass
    def logout(self, mind):
        pass

class IAvatarFactory(components.Interface):
    def loadAvatar(self, avatarId):
        pass

class Realm:
    __implements__ = portal.IRealm
    def __init__(self, factory):
        self.factory = factory
    def requestAvatar(self, avatarId, mind, *interfaces):
        try:
            avatar = self.factory(avatarId)
        except LookupError:
            raise NotImplementedError("object does not exist")
        for interface in interfaces:
            o = interface(avatar, None)
            if o is not None:
                break
        else:
            raise NotImplementedError("cannot follow specified interface")
        conn = IAvatar(avatar, _nullAvatar)
        conn.connect(mind)
        return interface, o, lambda: conn.logout(mind)

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
# Use: Realm(AvatarFactory())
#
# ------------------------------------------------------------------
# Example: (based on twisted/manhole/service.py)
# class ConnectedPerspective(components.Adapter):
#
#     __implements__ = IAvatar
#
#     def connect(self, mind):
#         self.original.attached(mind)
#
#     def logout(self, mind):
#         self.original.detached(mind)
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
# Use: Realm(PersistentFactory(AvatarFactory(service)))
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
# Use: Realm(MarkingFactory(resource, nonauthenticated))
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
# Use: Realm(SimpleFactory())
#
# ------------------------------------------------
# Example: (based on doc/examples/sshsimpleserver.py)
# 
# class SSHFactory:
#    __implements__ = IAvatarFactory
#    requestAvatar = SSHAvatar
#
# Use: Realm(SSHFactory())
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
# Use: Realm(SimpleFactory())
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
# Use: Realm(IAvatarFactory(MaildirDirdbmDomain(service, root, postmaster))
# Discussion: should Realm cast to IAvatarFactory?
#
# --------------------------------------------
# Example: (based on sandbox/glyph/dynademo/login.py
#
# class _LoggedInAvatar(AvatarAdapter):
#     def logout(self, mind):
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
