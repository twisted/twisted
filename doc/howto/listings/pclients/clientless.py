from twisted.cred import perspective

class ClientlessPerspective(perspective.Perspective):
    """I have no notion of 'client' whatsoever.

    I may still have methods which carry out actions and/or return
    objects (perspective_ methods and Referenceable objects, in the
    case of PB), but I take no notice when clients attach or detach
    from me.  Nor do I push data to clients; the only data they
    receive from me is the return values of any methods they choose to
    call.
    """
    pass
