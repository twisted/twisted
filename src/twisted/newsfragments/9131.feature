t.protocol.policies.TimeoutMixin.setTimeout and
t.protocol.policies.TimeoutProtocol.cancelTimeout
(used in t.protocol.policies.TimeoutFactory)
no longer raise a t.internet.error.AlreadyCancelled exception
when calling them for an already cancelled timeout.