#!/usr/bin/env python
# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Parser for PPAPI IDL """

#
# IDL Parser
#
# The parser is uses the PLY yacc library to build a set of parsing rules based
# on WebIDL.
#
# WebIDL, and WebIDL grammar can be found at:
#   http://dev.w3.org/2006/webapi/WebIDL/
# PLY can be found at:
#   http://www.dabeaz.com/ply/
#
# The parser generates a tree by recursively matching sets of items against
# defined patterns.  When a match is made, that set of items is reduced
# to a new item.   The new item can provide a match for parent patterns.
# In this way an AST is built (reduced) depth first.
#

#
# Disable check for line length and Member as Function due to how grammar rules
# are defined with PLY
#
# pylint: disable=R0201
# pylint: disable=C0301

import os.path
import sys
import time

from idl_ppapi_lexer import IDLPPAPILexer
from idl_parser import IDLParser, ListFromConcat, ParseFile
from idl_node import IDLAttribute, IDLNode

class IDLPPAPIParser(IDLParser):
#
# We force all input files to start with two comments.  The first comment is a
# Copyright notice followed by a file comment and finally by file level
# productions.
#
  # [0] Insert a TOP definition for Copyright and Comments
  def p_Top(self, p):
    """Top : COMMENT COMMENT Definitions"""
    Copyright = self.BuildComment('Copyright', p, 1)
    Filedoc = self.BuildComment('Comment', p, 2)
    p[0] = ListFromConcat(Copyright, Filedoc, p[3])

#
#The parser is based on the WebIDL standard.  See:
# http://www.w3.org/TR/WebIDL/#idl-grammar
#
  # [1]
  def p_Definitions(self, p):
    """Definitions : ExtendedAttributeList Definition Definitions
           | """
    if len(p) > 1:
      p[2].AddChildren(p[1])
      p[0] = ListFromConcat(p[2], p[3])

      # [2] Add INLINE definition
  def p_Definition(self, p):
    """Definition : CallbackOrInterface
                  | Partial
                  | Dictionary
                  | Exception
                  | Enum
                  | Typedef
                  | ImplementsStatement
                  | Label
                  | Inline"""
    p[0] = p[1]

  def p_Inline(self, p):
    """Inline : INLINE"""
    words = p[1].split()
    name = self.BuildAttribute('NAME', words[1])
    lines = p[1].split('\n')
    value = self.BuildAttribute('VALUE', '\n'.join(lines[1:-1]) + '\n')
    children = ListFromConcat(name, value)
    p[0] = self.BuildProduction('Inline', p, 1, children)

#
# Label
#
# A label is a special kind of enumeration which allows us to go from a
# set of version numbrs to releases
#
  def p_Label(self, p):
    """Label : LABEL identifier '{' LabelList '}' ';'"""
    p[0] = self.BuildNamed('Label', p, 2, p[4])

  def p_LabelList(self, p):
    """LabelList : identifier '=' float LabelCont"""
    val  = self.BuildAttribute('VALUE', p[3])
    label = self.BuildNamed('LabelItem', p, 1, val)
    p[0] = ListFromConcat(label, p[4])

  def p_LabelCont(self, p):
    """LabelCont : ',' LabelList
                 |"""
    if len(p) > 1: p[0] = p[2]

  def p_LabelContError(self, p):
    """LabelCont : error LabelCont"""
    p[0] = p[2]

  # [27]
  def p_ConstValue(self, p):
    """ConstValue : integer
                  | integer LSHIFT integer
                  | integer RSHIFT integer"""
    val = str(p[1])
    if len(p) > 2:
      val = "%s %s %s" % (p[1], p[2], p[3])
    p[0] = ListFromConcat(self.BuildAttribute('TYPE', 'integer'),
                          self.BuildAttribute('VALUE', val))

  def p_ConstValueStr(self, p):
    """ConstValue : string"""
    p[0] = ListFromConcat(self.BuildAttribute('TYPE', 'string'),
                          self.BuildAttribute('VALUE', p[1]))

  # Boolean & Float Literals area already BuildAttributes
  def p_ConstValueLiteral(self, p):
    """ConstValue : FloatLiteral
                  | BooleanLiteral """
    p[0] = p[1]

  # [21]
  def p_EnumValueList(self, p):
    """EnumValueList : EnumValue EnumValues"""
    p[0] = ListFromConcat(p[1], p[2])

  # [22]
  def p_EnumValues(self, p):
    """EnumValues : ',' EnumValue EnumValues
                  |"""
    if len(p) > 1:
      p[0] = ListFromConcat(p[2], p[3])

  def p_EnumValue(self, p):
    """EnumValue : ExtendedAttributeList identifier
                 | ExtendedAttributeList identifier '=' ConstValue"""
    p[0] = self.BuildNamed('EnumItem', p, 2, p[1])
    if len(p) > 3:
      p[0].AddChildren(p[4])

  def p_PrimitiveType(self, p):
    """PrimitiveType : IntegerType
                     | UnsignedIntegerType
                     | FloatType
                     | HandleType
                     | PointerType"""
    if type(p[1]) == str:
      p[0] = self.BuildNamed('PrimitiveType', p, 1)
    else:
      p[0] = p[1]

  def p_PointerType(self, p):
    """PointerType : STR_T
                   | MEM_T
                   | CSTR_T
                   | INTERFACE_T
                   | NULL"""
    p[0] = p[1]

  def p_HandleType(self, p):
    """HandleType : HANDLE_T
                  | PP_FILEHANDLE"""
    p[0] = p[1]

  # [66]
  def p_FloatType(self, p):
    """FloatType : FLOAT_T
                 | DOUBLE_T"""
    p[0] = p[1]

  # [67]
  def p_UnsignedIntegerType(self, p):
    """UnsignedIntegerType : UINT8_T
                           | UINT16_T
                           | UINT32_T
                           | UINT64_T"""
    p[0] = p[1]


  # [68]
  def p_IntegerType(self, p):
    """IntegerType : CHAR
                   | INT8_T
                   | INT16_T
                   | INT32_T
                   | INT64_T"""
    p[0] = p[1]

  # These targets are no longer used
  def p_OptionalLong(self, p):
    """ """
    pass

  def p_UnrestrictedFloatType(self, p):
    """ """
    pass

  def p_null(self, p):
    """ """
    pass

  def __init__(self, lexer, verbose=False, debug=False, mute_error=False):
    IDLParser.__init__(self, lexer, verbose, debug, mute_error)


def main(argv):
  nodes = []
  parser = IDLPPAPIParser(IDLPPAPILexer())
  errors = 0

  for filename in argv:
    filenode = ParseFile(parser, filename)
    if filenode:
      errors += filenode.GetProperty('ERRORS')
      nodes.append(filenode)

  ast = IDLNode('AST', '__AST__', 0, 0, nodes)

  print '\n'.join(ast.Tree(accept_props=['PROD', 'TYPE', 'VALUE']))
  if errors:
    print '\nFound %d errors.\n' % errors


  return errors


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))