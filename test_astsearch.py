import ast
import types
import unittest

from astcheck import assert_ast_like
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
        assert not hasattr(pat, 'left')
        assert not hasattr(pat, 'right')
    
    def test_wildcard_body(self):
        pat = prepare_pattern('if True: ?\nelse: ?')
        assert isinstance(pat, ast.If)
        assert pat.body is must_exist_checker
        assert pat.orelse is must_exist_checker
        
        pat2 = prepare_pattern('if True: ?')
        assert isinstance(pat2, ast.If)
        assert pat.body is must_exist_checker
        assert not hasattr(pat2, 'orelse')
    
    def test_name_or_attr(self):
        pat = prepare_pattern('a = 1')
        assert_ast_like(pat, ast.Assign(value=ast.Num(1)))
        assert isinstance(pat.targets[0], types.FunctionType)