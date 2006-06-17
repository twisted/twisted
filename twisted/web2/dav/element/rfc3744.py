##
# Copyright (c) 2005 Apple Computer, Inc. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# DRI: Wilfredo Sanchez, wsanchez@apple.com
##

"""
RFC 3744 (WebDAV Access Control Protocol) XML Elements

This module provides XML element definitions for use with WebDAV.

See RFC 3744: http://www.ietf.org/rfc/rfc3744.txt
"""

from twisted.web2.dav.element.base import *

##
# Section 3 (Privileges)
##

class Read (WebDAVEmptyElement):
    """
    Privilege which controls methods that return information about the state
    of a resource, including the resource's properties. (RFC 3744, section
    3.1)
    """
    name = "read"

# For DAV:write element (RFC 3744, section 3.2) see Write class above.

class WriteProperties (WebDAVEmptyElement):
    """
    Privilege which controls methods that modify the dead properties of a
    resource. (RFC 3744, section 3.3)
    """
    name = "write-properties"

class WriteContent (WebDAVEmptyElement):
    """
    Privilege which controls methods that modify the content of an existing
    resource. (RFC 3744, section 3.4)
    """
    name = "write-content"

class Unlock (WebDAVEmptyElement):
    """
    Privilege which controls the use of the UNLOCK method by a principal other
    than the lock owner. (RFC 3744, section 3.5)
    """
    name = "unlock"

class ReadACL (WebDAVEmptyElement):
    """
    Privilege which controls the use of the PROPFIND method to retrieve the
    DAV:acl property of a resource. (RFC 3744, section 3.6)
    """
    name = "read-acl"

class ReadCurrentUserPrivilegeSet (WebDAVEmptyElement):
    """
    Privilege which controls the use of the PROPFIND method to retrieve the
    DAV:current-user-privilege-set property of a resource. (RFC 3744, section
    3.7)
    """
    name = "read-current-user-privilege-set"

class WriteACL (WebDAVEmptyElement):
    """
    Privilege which controls the use of the ACL method to modify the DAV:acl
    property of a resource. (RFC 3744, section 3.8)
    """
    name = "write-acl"

class Bind (WebDAVEmptyElement):
    """
    Privilege which allows a method to add a new member URL from the a
    collection resource. (RFC 3744, section 3.9)
    """
    name = "bind"

class Unbind (WebDAVEmptyElement):
    """
    Privilege which allows a method to remove a member URL from the a collection
    resource. (RFC 3744, section 3.10)
    """
    name = "unbind"

class All (WebDAVEmptyElement):
    """
    Aggregate privilege that contains the entire set of privileges that can be
    applied to a resource. (RFC 3744, section 3.11)
    Principal which matches all users. (RFC 3744, section 5.5.1)
    """
    name = "all"

##
# Section 4 (Principal Properties)
##

class Principal (WebDAVElement):
    """
    Indicates a principal resource type. (RFC 3744, section 4)
    Identifies the principal to which an ACE applies. (RFC 3744, section 5.5.1)
    """
    name = "principal"

    allowed_children = {
        (dav_namespace, "href"           ): (0, 1),
        (dav_namespace, "all"            ): (0, 1),
        (dav_namespace, "authenticated"  ): (0, 1),
        (dav_namespace, "unauthenticated"): (0, 1),
        (dav_namespace, "property"       ): (0, 1),
        (dav_namespace, "self"           ): (0, 1),
    }

    def __init__(self, *children, **attributes):
        super(Principal, self).__init__(*children, **attributes)

        if len(self.children) > 1:
            raise ValueError(
                "Exactly one of DAV:href, DAV:all, DAV:authenticated, "
                "DAV:unauthenticated, DAV:property or DAV:self is required for "
                "%s, got: %r"
                % (self.sname(), self.children)
            )

class AlternateURISet (WebDAVElement):
    """
    Property which contains the URIs of network resources with additional
    descriptive information about the principal. (RFC 3744, section 4.1)
    """
    name = "alternate-uri-set"
    hidden = True
    protected = True

    allowed_children = { (dav_namespace, "href"): (0, None) }

class PrincipalURL (WebDAVElement):
    """
    Property which contains the URL that must be used to identify this principal
    in an ACL request. (RFC 3744, section 4.2)
    """
    name = "principal-url"
    hidden = True
    protected = True

    allowed_children = { (dav_namespace, "href"): (0, 1) }

class GroupMemberSet (WebDAVElement):
    """
    Property which identifies the principals that are direct members of a group
    principal.
    (RFC 3744, section 4.3)
    """
    name = "group-member-set"
    hidden = True

    allowed_children = { (dav_namespace, "href"): (0, None) }

class GroupMembership (WebDAVElement):
    """
    Property which identifies the group principals in which a principal is
    directly a member. (RFC 3744, section 4.4)
    """
    name = "group-membership"
    hidden = True
    protected = True

    allowed_children = { (dav_namespace, "href"): (0, None) }

##
# Section 5 (Access Control Properties)
##

# For DAV:owner element (RFC 3744, section 5.1) see Owner class above.

class Group (WebDAVElement):
    """
    Property which identifies a particular principal as being the group
    principal of a resource. (RFC 3744, section 5.2)
    """
    name = "group"
    hidden = True
    #protected = True # may be protected, per RFC 3744, section 5.2

    allowed_children = { (dav_namespace, "href"): (0, 1) }

class SupportedPrivilegeSet (WebDAVElement):
    """
    Property which identifies the privileges defined for a resource. (RFC 3744,
    section 5.3)
    """
    name = "supported-privilege-set"
    hidden = True
    protected = True

    allowed_children = { (dav_namespace, "supported-privilege"): (0, None) }

class SupportedPrivilege (WebDAVElement):
    """
    Identifies a privilege defined for a resource. (RFC 3744, section 5.3)
    """
    name = "supported-privilege"

    allowed_children = {
        (dav_namespace, "privilege"          ): (1, 1),
        (dav_namespace, "abstract"           ): (0, 1),
        (dav_namespace, "description"        ): (1, 1),
        (dav_namespace, "supported-privilege"): (0, None),
    }

class Privilege (WebDAVElement):
    """
    Identifies a privilege. (RFC 3744, sections 5.3 and 5.5.1)
    """
    name = "privilege"

    allowed_children = { WebDAVElement: (0, None) }

class Abstract (WebDAVElement):
    """
    Identifies a privilege as abstract. (RFC 3744, section 5.3)
    """
    name = "abstract"

class Description (WebDAVTextElement):
    """
    A human-readable description of what privilege controls access to. (RFC
    3744, sections 5.3 and 9.5)
    """
    name = "description"
    allowed_attributes = { "xml:lang": True }

class CurrentUserPrivilegeSet (WebDAVElement):
    """
    Property which contains the exact set of privileges (as computer by the
    server) granted to the currently authenticated HTTP user. (RFC 3744, section
    5.4)
    """
    name = "current-user-privilege-set"
    hidden = True
    protected = True

    allowed_children = { (dav_namespace, "privilege"): (0, None) }

# For DAV:privilege element (RFC 3744, section 5.4) see Privilege class above.

class ACL (WebDAVElement):
    """
    Property which specifies the list of access control entries which define
    what privileges are granted to which users for a resource. (RFC 3744,
    section 5.5)
    """
    name = "acl"
    hidden = True
    protected = True

    allowed_children = { (dav_namespace, "ace"): (0, None) }

class ACE (WebDAVElement):
    """
    Specifies the list of access control entries which define what privileges
    are granted to which users for a resource. (RFC 3744, section 5.5)
    """
    name = "ace"

    allowed_children = {
        (dav_namespace, "principal"): (0, 1),
        (dav_namespace, "invert"   ): (0, 1),
        (dav_namespace, "grant"    ): (0, 1),
        (dav_namespace, "deny"     ): (0, 1),
        (dav_namespace, "protected"): (0, 1),
        (dav_namespace, "inherited"): (0, 1),
    }

    def __init__(self, *children, **attributes):
        super(ACE, self).__init__(*children, **attributes)

        self.principal  = None
        self.invert     = None
        self.allow      = None
        self.privileges = None
        self.inherited  = None
        self.protected  = False

        for child in self.children:
            namespace, name = child.qname()

            assert namespace == dav_namespace

            if name in ("principal", "invert"):
                if self.principal is not None:
                    raise ValueError(
                        "Only one of DAV:principal or DAV:invert allowed in %s, got: %s"
                        % (self.sname(), self.children)
                    )
                if name == "invert":
                    self.invert    = True
                    self.principal = child.children[0]
                else:
                    self.invert    = False
                    self.principal = child

            elif name in ("grant", "deny"):
                if self.allow is not None:
                    raise ValueError(
                        "Only one of DAV:grant or DAV:deny allowed in %s, got: %s"
                        % (self.sname(), self.children)
                    )
                self.allow      = (name == "grant")
                self.privileges = child.children

            elif name == "inherited":
                self.inherited = str(child.children[0])

            elif name == "protected":
                self.protected = True

        if self.principal is None:
            raise ValueError(
                "One of DAV:principal or DAV:invert is required in %s, got: %s"
                % (self.sname(), self.children)
            )
        assert self.invert is not None

        if self.allow is None:
            raise ValueError(
                "One of DAV:grant or DAV:deny is required in %s, got: %s"
                % (self.sname(), self.children)
            )
        assert self.privileges is not None

# For DAV:principal element (RFC 3744, section 5.5.1) see Principal class above.

# For DAV:all element (RFC 3744, section 5.5.1) see All class above.

class Authenticated (WebDAVEmptyElement):
    """
    Principal which matches authenticated users. (RFC 3744, section 5.5.1)
    """
    name = "authenticated"

class Unauthenticated (WebDAVEmptyElement):
    """
    Principal which matches unauthenticated users. (RFC 3744, section 5.5.1)
    """
    name = "unauthenticated"

# For DAV:property element (RFC 3744, section 5.5.1) see Property class above.

class Self (WebDAVEmptyElement):
    """
    Principal which matches a user if a resource is a principal and the user
    matches the resource. (RFC 3744, sections 5.5.1 and 9.3)
    """
    name = "self"

class Invert (WebDAVEmptyElement):
    """
    Principal which matches a user if the user does not match the principal
    contained by this principal. (RFC 3744, section 5.5.1)
    """
    name = "invert"

    allowed_children = { (dav_namespace, "principal"): (1, 1) }

class Grant (WebDAVElement):
    """
    Grants the contained privileges to a principal. (RFC 3744, section 5.5.2)
    """
    name = "grant"

    allowed_children = { (dav_namespace, "privilege"): (1, None) }

class Deny (WebDAVElement):
    """
    Denies the contained privileges to a principal. (RFC 3744, section 5.5.2)
    """
    name = "deny"

    allowed_children = { (dav_namespace, "privilege"): (1, None) }

# For DAV:privilege element (RFC 3744, section 5.5.2) see Privilege class above.

class Protected (WebDAVEmptyElement):
    """
    Identifies an ACE as protected. (RFC 3744, section 5.5.3)
    """
    name = "protected"

class Inherited (WebDAVElement):
    """
    Indicates that an ACE is inherited from the resource indentified by the
    contained DAV:href element. (RFC 3744, section 5.5.4)
    """
    name = "inherited"

    allowed_children = { (dav_namespace, "href"): (1, 1) }

class ACLRestrictions (WebDAVElement):
    """
    Property which defines the types of ACLs supported by this server, to avoid
    clients needlessly getting errors. (RFC 3744, section 5.6)
    """
    name = "acl-restrictions"
    hidden = True
    protected = True

    allowed_children = {
        (dav_namespace, "grant-only"        ): (0, 1),
        (dav_namespace, "no-invert"         ): (0, 1),
        (dav_namespace, "deny-before-grant" ): (0, 1),
        (dav_namespace, "required-principal"): (0, 1),
    }

class GrantOnly (WebDAVEmptyElement):
    """
    Indicates that ACEs with deny clauses are not allowed. (RFC 3744, section
    5.6.1)
    """
    name = "grant-only"

class NoInvert (WebDAVEmptyElement):
    """
    Indicates that ACEs with the DAV:invert element are not allowed. (RFC 3744,
    section 5.6.2)
    """
    name = "no-invert"

class DenyBeforeGrant (WebDAVEmptyElement):
    """
    Indicates that all deny ACEs must precede all grant ACEs. (RFC 3744, section
    5.6.3)
    """
    name = "deny-before-grant"

class RequiredPrincipal (WebDAVElement):
    """
    Indicates which principals must have an ACE defined in an ACL. (RFC 3744,
    section 5.6.4)
    """
    name = "required-principal"

    allowed_children = {
        (dav_namespace, "all"            ): (0, 1),
        (dav_namespace, "authenticated"  ): (0, 1),
        (dav_namespace, "unauthenticated"): (0, 1),
        (dav_namespace, "self"           ): (0, 1),
        (dav_namespace, "href"           ): (0, None),
        (dav_namespace, "property"       ): (0, None),
    }

    def __init__(self, *children, **attributes):
        super(RequiredPrincipal, self).__init__(*children, **attributes)

        type = None

        for child in self.children:
            if type is None:
                type = child.qname()
            elif child.qname() != type:
                raise ValueError(
                    "Only one of DAV:all, DAV:authenticated, DAV:unauthenticated, "
                    "DAV:self, DAV:href or DAV:property allowed for %s, got: %s"
                    % (self.sname(), self.children)
                )

class InheritedACLSet (WebDAVElement):
    """
    Property which contains a set of URLs that identify other resources that
    also control the access to this resource. (RFC 3744, section 5.7)
    """
    name = "inherited-acl-set"
    hidden = True
    protected = True

    allowed_children = { (dav_namespace, "href"): (0, None) }

class PrincipalCollectionSet (WebDAVElement):
    """
    Property which contains a set of URLs that identify the root collections
    that contain the principals that are available on the server that implements
    a resource. (RFC 3744, section 5.8)
    """
    name = "principal-collection-set"
    hidden = True
    protected = True

    allowed_children = { (dav_namespace, "href"): (0, None) }

##
# Section 7 (Access Control and existing methods)
##

class NeedPrivileges (WebDAVElement):
    """
    Error which indicates insufficient privileges. (RFC 3744, section 7.1.1)
    """
    name = "need-privileges"

    allowed_children = { (dav_namespace, "resource"): (0, None) }

class Resource (WebDAVElement):
    """
    Identifies which resource had insufficient privileges. (RFC 3744, section
    7.1.1)
    """
    name = "resource"

    allowed_children = {
        (dav_namespace, "href"     ): (1, 1),
        (dav_namespace, "privilege"): (1, 1),
    }

##
# Section 9 (Access Control Reports)
##

class ACLPrincipalPropSet (WebDAVElement):
    """
    Report which returns, for all principals in the DAV:acl property (of the
    resource identified by the Request-URI) that are identified by http(s) URLs
    or by a DAV:property principal, the value of the properties specified in the
    REPORT request body. (RFC 3744, section 9.2)
    """
    name = "acl-principal-prop-set"

    allowed_children = { WebDAVElement: (0, None) }

    def __init__(self, *children, **attributes):
        super(ACLPrincipalPropSet, self).__init__(*children, **attributes)

        prop = False
        
        for child in self.children:
            if child.qname() == (dav_namespace, "prop"):
                if prop:
                    raise ValueError(
                        "Only one DAV:prop allowed for %s, got: %s"
                        % (self.sname(), self.children)
                    )
                prop = True

class PrincipalMatch (WebDAVElement):
    """
    Report used to identify all members (at any depth) of the collection
    identified by the Request-URI that are principals and that match the current
    user. (RFC 3744, section 9.3)
    """
    name = "principal-match"

    allowed_children = {
        (dav_namespace, "principal-property"): (0, 1),
        (dav_namespace, "self"              ): (0, 1),
        (dav_namespace, "prop"              ): (0, 1),
    }

    def __init__(self, *children, **attributes):
        super(PrincipalMatch, self).__init__(*children, **attributes)

        principalPropertyOrSelf = False

        for child in self.children:
            namespace, name = child.qname()

            if name in ("principal-property", "self"):
                if principalPropertyOrSelf:
                    raise ValueError(
                        "Only one of DAV:principal-property or DAV:self allowed in %s, got: %s"
                        % (self.sname(), self.children)
                    )
                principalPropertyOrSelf = True

        if not principalPropertyOrSelf:
            raise ValueError(
                "One of DAV:principal-property or DAV:self is required in %s, got: %s"
                % (self.sname(), self.children)
            )

class PrincipalProperty (WebDAVElement):
    """
    Identifies a property. (RFC 3744, section 9.3)
    """
    name = "principal-property"

    allowed_children = { WebDAVElement: (0, None) }

# For DAV:self element (RFC 3744, section 9.3) see Self class above.

class PrincipalPropertySearch (WebDAVElement):
    """
    Report which performs a search for all principals whose properties contain
    character data that matches the search criteria specified in the request.
    (RFC 3744, section 9.4)
    """
    name = "principal-property-search"

    allowed_children = {
        (dav_namespace, "property-search"                  ): (1, None),
        (dav_namespace, "prop"                             ): (0, 1),
        (dav_namespace, "apply-to-principal-collection-set"): (0, 1),
    }

class PropertySearch (WebDAVElement):
    """
    Contains a DAV:prop element enumerating the properties to be searched and a
    DAV:match element, containing the search string. (RFC 3744, section 9.4)
    """
    name = "property-search"

    allowed_children = {
        (dav_namespace, "prop" ): (1, 1),
        (dav_namespace, "match"): (1, 1),
    }

class Match (WebDAVTextElement):
    """
    Contains a search string. (RFC 3744, section 9.4)
    """
    name = "match"

class PrincipalSearchPropertySet (WebDAVElement):
    """
    Report which identifies those properties that may be searched using the
    DAV:principal-property-search report. (RFC 3744, section 9.5)
    """
    name = "principal-search-property-set"

    allowed_children = { (dav_namespace, "principal-search-property"): (0, None) }

class PrincipalSearchProperty (WebDAVElement):
    """
    Contains exactly one searchable property, and a description of the property.
    (RFC 3744, section 9.5)
    """
    name = "principal-search-property"

    allowed_children = {
        (dav_namespace, "prop"       ): (1, 1),
        (dav_namespace, "description"): (1, 1),
    }

# For DAV:description element (RFC 3744, section 9.5) see Description class above.
