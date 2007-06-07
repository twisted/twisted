# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

# DO NOT EDIT xpathparser.py!
#
# It is generated from xpathparser.g using Yapps. Make needed changes there.
# This also means that the generated Python may not conform to Twisted's coding
# standards.

# HOWTO Generate me:
# 1.) Grab a copy of yapps2: http://theory.stanford.edu/~amitp/Yapps/
#     (available on debian by "apt-get install -t unstable yapps2")
# 2.) Generate the grammar as usual
# 3.) Hack the output to read:
#
#         import yappsrt as runtime
#
#       instead of
#
#         from yapps import runtime

from twisted.words.xish.xpath import AttribValue, BooleanValue, CompareValue
from twisted.words.xish.xpath import Function, IndexValue, LiteralValue
from twisted.words.xish.xpath import _AnyLocation, _Location

%%
parser XPathParser:
        ignore:             "\\s+"
        token INDEX:        "[0-9]+"
        token WILDCARD:     "\*"
        token IDENTIFIER:   "[a-zA-Z][a-zA-Z0-9_\-]*"
        token ATTRIBUTE:    "\@[a-zA-Z][a-zA-Z0-9_\-]*"
        token FUNCNAME:     "[a-zA-Z][a-zA-Z0-9_]*"
        token CMP_EQ:       "\="
        token CMP_NE:       "\!\="
        token STR_DQ:       '"([^"]|(\\"))*?"'
        token STR_SQ:       "'([^']|(\\'))*?'"
        token OP_AND:       "and"
        token OP_OR:        "or"
        token END:          "$"

        rule XPATH:      PATH {{ result = PATH; current = result }}
                           ( PATH {{ current.childLocation = PATH; current = current.childLocation }} ) * END
                           {{ return  result }}

        rule PATH:       ("/" {{ result = _Location() }} | "//" {{ result = _AnyLocation() }} )
                           ( IDENTIFIER {{ result.elementName = IDENTIFIER }} | WILDCARD {{ result.elementName = None }} )
                           ( "\[" PREDICATE {{ result.predicates.append(PREDICATE) }} "\]")*
                           {{ return result }}

        rule PREDICATE:  EXPR  {{ return EXPR }} |
                         INDEX {{ return IndexValue(INDEX) }}

        rule EXPR:       FACTOR {{ e = FACTOR }}
                           ( BOOLOP FACTOR {{ e = BooleanValue(e, BOOLOP, FACTOR) }} )*
                           {{ return e }}

        rule BOOLOP:     ( OP_AND {{ return OP_AND }} | OP_OR {{ return OP_OR }} )

        rule FACTOR:     TERM {{ return TERM }}
                           | "\(" EXPR "\)" {{ return EXPR }}

        rule TERM:       VALUE            {{ t = VALUE }}
                           [ CMP VALUE  {{ t = CompareValue(t, CMP, VALUE) }} ]
                                          {{ return t }}

        rule VALUE:      "@" IDENTIFIER   {{ return AttribValue(IDENTIFIER) }} |
                         FUNCNAME         {{ f = Function(FUNCNAME); args = [] }}
                           "\(" [ VALUE      {{ args.append(VALUE) }}
                             (
                               "," VALUE     {{ args.append(VALUE) }}
                             )*
                           ] "\)"           {{ f.setParams(*args); return f }} |
                         STR              {{ return LiteralValue(STR[1:len(STR)-1]) }}

        rule CMP: (CMP_EQ  {{ return CMP_EQ }} | CMP_NE {{ return CMP_NE }})
        rule STR: (STR_DQ  {{ return STR_DQ }} | STR_SQ {{ return STR_SQ }})
