import ast
from io import StringIO
import types
import unittest

from astcheck import assert_ast_like, listmiddle
from astsearch import prepare_pattern, ASTPatternFinder, must_exist_checker

class PreparePatternTests(unittest.TestCase):
    def test_plain(self):
        pat = prepare_pattern('1/2')
        assert_ast_like(pat, ast.BinOp(left=ast.Num(n=1),
                                       op=ast.Div(),
                                       right=ast.Num(n=2))
                        )
    
    def test_simple_wildcard(self):
        pat = prepare_pattern('?/?')
        assert_ast_like(pat, ast.BinOp(op=ast.Div()))
        assert pat.left is must_exist_checker
        assert pat.right is must_exist_checker
    
    def test_wildcard_body(self):
        pat = prepare_pattern('if True: ??\nelse: ??')
        assert isinstance(pat, ast.If)
        assert pat.body is must_exist_checker
        assert pat.orelse is must_exist_checker
        
        pat2 = prepare_pattern('if True: ??')
        assert isinstance(pat2, ast.If)
        assert pat.body is must_exist_checker
        assert not hasattr(pat2, 'orelse')
    
    def test_wildcard_body_part(self):
        pat = prepare_pattern("def foo():\n  ??\n  return a")
        assert isinstance(pat, ast.FunctionDef)
        assert isinstance(pat.body, listmiddle)
        assert_ast_like(pat.body.back[0], ast.Return(ast.Name(id='a')))

    def test_name_or_attr(self):
        pat = prepare_pattern('a = 1')
        assert_ast_like(pat, ast.Assign(value=ast.Num(1)))
        assert isinstance(pat.targets[0], types.FunctionType)

division_sample = """#!/usr/bin/python3
'not / division'
1/2
a.b/c
# 5/6
78//8  # FloorDiv is not the same

def divide(x, y):
    return x/y
"""

if_sample = """
if a:
    pass
else:
    pass

if b:
    pass
"""

class PatternFinderTests(unittest.TestCase):
    def assert_no_more(self, it):
        with self.assertRaises(StopIteration):
            next(it)

    def test_plain(self):
        pat = ast.BinOp(left=ast.Num(1), right=ast.Num(2), op=ast.Div())
        it = ASTPatternFinder(pat).scan_file(StringIO(division_sample))
        assert next(it).left.n == 1
        self.assert_no_more(it)

    def test_all_divisions(self):
        pat = ast.BinOp(op=ast.Div())
        it = ASTPatternFinder(pat).scan_file(StringIO(division_sample))
        assert_ast_like(next(it), ast.BinOp(left=ast.Num(n=1)))
        assert_ast_like(next(it), ast.BinOp(right=ast.Name(id='c')))
        assert_ast_like(next(it), ast.BinOp(left=ast.Name(id='x')))
        self.assert_no_more(it)

    def test_block_must_exist(self):
        pat = ast.If(orelse=must_exist_checker)
        it = ASTPatternFinder(pat).scan_file(StringIO(if_sample))
        assert_ast_like(next(it), ast.If(test=ast.Name(id='a')))
        self.assert_no_more(it)