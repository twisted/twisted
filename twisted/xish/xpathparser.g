
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# NOTE!
# NOTE! Actual grammar is at the end of the file
# NOTE!

# HOWTO Generate me:
# 1.) Grab a copy of yapps2: http://theory.stanford.edu/~amitp/Yapps/
# 2.) Hack it to not add a "import yappsrt" in the output file
# 3.) Generate the grammar as usual


# Yapps 2.0 Runtime
#
# This module is needed to run generated parsers.

import string, re

class SyntaxError(Exception):
    """When we run into an unexpected token, this is the exception to use"""
    def __init__(self, pos=-1, msg="Bad Token"):
        Exception.__init__(self)
	self.pos = pos
	self.msg = msg
    def __repr__(self):
	if self.pos < 0: return "#<syntax-error>"
	else: return "SyntaxError[@ char %s: %s]" % (repr(self.pos), self.msg)

class NoMoreTokens(Exception):
    """Another exception object, for when we run out of tokens"""
    pass

class Scanner:
    def __init__(self, patterns, ignore, input):
	"""Patterns is [(terminal,regex)...]
        Ignore is [terminal,...];
	Input is a string"""
	self.tokens = []
	self.restrictions = []
	self.input = input
	self.pos = 0
	self.ignore = ignore
	# The stored patterns are a pair (compiled regex,source
	# regex).  If the patterns variable passed in to the
	# constructor is None, we assume that the class already has a
	# proper .patterns list constructed
        if patterns is not None:
            self.patterns = []
            for k, r in patterns:
                self.patterns.append( (k, re.compile(r)) )
	
    def token(self, i, restrict=0):
	"""Get the i'th token, and if i is one past the end, then scan
	for another token; restrict is a list of tokens that
	are allowed, or 0 for any token."""
	if i == len(self.tokens): self.scan(restrict)
	if i < len(self.tokens):
	    # Make sure the restriction is more restricted
	    if restrict and self.restrictions[i]:
		for r in restrict:
		    if r not in self.restrictions[i]:
			raise NotImplementedError("Unimplemented: restriction set changed")
	    return self.tokens[i]
	raise NoMoreTokens()
    
    def __repr__(self):
	"""Print the last 10 tokens that have been scanned in"""
	output = ''
	for t in self.tokens[-10:]:
	    output = '%s\n  (@%s)  %s  =  %s' % (output,t[0],t[2],repr(t[3]))
	return output
    
    def scan(self, restrict):
	"""Should scan another token and add it to the list, self.tokens,
	and add the restriction to self.restrictions"""
	# Keep looking for a token, ignoring any in self.ignore
	while 1:
	    # Search the patterns for the longest match, with earlier
	    # tokens in the list having preference
	    best_match = -1
	    best_pat = '(error)'
	    for p, regexp in self.patterns:
		# First check to see if we're ignoring this token
		if restrict and p not in restrict and p not in self.ignore:
		    continue
		m = regexp.match(self.input, self.pos)
		if m and len(m.group(0)) > best_match:
		    # We got a match that's better than the previous one
		    best_pat = p
		    best_match = len(m.group(0))
		    
	    # If we didn't find anything, raise an error
	    if best_pat == '(error)' and best_match < 0:
		msg = "Bad Token"
		if restrict:
		    msg = "Trying to find one of "+string.join(restrict,", ")
		raise SyntaxError(self.pos, msg)

	    # If we found something that isn't to be ignored, return it
	    if best_pat not in self.ignore:
		# Create a token with this data
		token = (self.pos, self.pos+best_match, best_pat,
			 self.input[self.pos:self.pos+best_match])
		self.pos = self.pos + best_match
		# Only add this token if it's not in the list
		# (to prevent looping)
		if not self.tokens or token != self.tokens[-1]:
		    self.tokens.append(token)
		    self.restrictions.append(restrict)
		return
	    else:
		# This token should be ignored ..
		self.pos = self.pos + best_match

class Parser:
    def __init__(self, scanner):
        self._scanner = scanner
        self._pos = 0
        
    def _peek(self, *types):
        """Returns the token type for lookahead; if there are any args
        then the list of args is the set of token types to allow"""
        tok = self._scanner.token(self._pos, types)
        return tok[2]
        
    def _scan(self, type):
        """Returns the matched text, and moves to the next token"""
        tok = self._scanner.token(self._pos, [type])
        if tok[2] != type:
            raise SyntaxError(tok[0], 'Trying to find '+type)
        self._pos = 1+self._pos
        return tok[3]



def print_error(input, err, scanner):
    """This is a really dumb long function to print error messages nicely."""
    p = err.pos
    # Figure out the line number
    line = string.count(input[:p], '\n')
    print err.msg+" on line "+repr(line+1)+":"
    # Now try printing part of the line
    text = input[max(p-80, 0):p+80]
    p = p - max(p-80, 0)

    # Strip to the left
    i = string.rfind(text[:p], '\n')
    j = string.rfind(text[:p], '\r')
    if i < 0 or (0 <= j < i): i = j
    if 0 <= i < p:
	p = p - i - 1
	text = text[i+1:]

    # Strip to the right
    i = string.find(text,'\n', p)
    j = string.find(text,'\r', p)
    if i < 0 or (0 <= j < i): i = j
    if i >= 0:
	text = text[:i]

    # Now shorten the text
    while len(text) > 70 and p > 60:
	# Cut off 10 chars
	text = "..." + text[10:]
	p = p - 7

    # Now print the string, along with an indicator
    print '> ',text
    print '> ',' '*p + '^'
    print 'List of nearby tokens:', scanner

def wrap_error_reporter(parser, rule):
    try: return getattr(parser, rule)()
    except SyntaxError, s:
        input = parser._scanner.input
        try:
            print_error(input, s, parser._scanner)
        except ImportError:
            print 'Syntax Error',s.msg,'on line',1+count(input[:s.pos], '\n')
    except NoMoreTokens:
        print 'Could not complete parsing; stopped around here:'
        print parser._scanner


from twisted.xish.xpath import _Location, IndexValue, CompareValue, AttribValue, LiteralValue, Function

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
        token END:          "$"

        rule XPATH:    PATH {{ result = PATH; current = result }}
                          ( PATH {{ current.childLocation = PATH; current = current.childLocation }} ) * END
                          {{ return  result }}

        rule PATH:          "/" {{ result = _Location() }}
                             ( IDENTIFIER {{ result.elementName = IDENTIFIER }} | WILDCARD {{ result.elementName = None }} )
                             ( "\[" PREDICATE {{ result.predicates.append(PREDICATE) }} "\]")*
                            {{ return result }}

        rule PREDICATE:  EXPR  {{ return EXPR }} | 
                         INDEX {{ return IndexValue(INDEX) }}

        rule EXPR:       VALUE            {{ e = VALUE }}
                           [ CMP VALUE  {{ e = CompareValue(e, CMP, VALUE) }} ]  
                                          {{ return e }}

        rule VALUE:      "@" IDENTIFIER   {{ return AttribValue(IDENTIFIER) }} | 
                         FUNCNAME         {{ f = Function(FUNCNAME); args = [] }}
                           "\("[ VALUE      {{ args.append(VALUE) }} 
                             (
                               "," VALUE     {{ args.append(VALUE) }} 
                             )*   
                           ] "\)"           {{ f.setParams(*args); return f }} | 
                         STR              {{ return LiteralValue(STR[1:len(STR)-1]) }}
        
        rule CMP: (CMP_EQ  {{ return CMP_EQ }} | CMP_NE {{ return CMP_NE }})
        rule STR: (STR_DQ  {{ return STR_DQ }} | STR_SQ {{ return STR_SQ }})



        
