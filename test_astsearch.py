import ast
from io import StringIO
import sys
import types
import unittest

from astcheck import assert_ast_like, listmiddle, name_or_attr
from astsearch import (
    prepare_pattern, ASTPatternFinder, must_exist_checker, must_not_exist_checker,
    ArgsDefChecker,
)

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
        assert (isinstance(pat.targets[0], types.FunctionType) \
                or isinstance(pat.targets[0], name_or_attr))

    def test_wildcard_call_args(self):
        pat = prepare_pattern("f(??)")
        assert isinstance(pat, ast.Call)
        assert isinstance(pat.args, listmiddle)
        assert pat.args.front == []
        assert pat.args.back == []
        assert not hasattr(pat, 'keywords')
        assert not hasattr(pat, 'starargs')
        assert not hasattr(pat, 'kwargs')

    def test_wildcard_some_call_args(self):
        pat = prepare_pattern("f(??, 1)")
        assert isinstance(pat.args, listmiddle)
        assert pat.args.front == []
        assert_ast_like(pat.args.back[0], ast.Num(n=1))
        if sys.version_info < (3, 5):
            assert pat.starargs is None
        assert pat.keywords == must_not_exist_checker

    def test_wildcard_call_keywords(self):
        pat = prepare_pattern("f(a=1, ??=??)")
        assert pat.args == must_not_exist_checker
        if sys.version_info < (3, 5):
            assert pat.starargs is None
        assert isinstance(pat.keywords, types.FunctionType)
        assert not hasattr(pat, 'kwargs')

    def test_wildcard_call_mixed_args(self):
        pat = prepare_pattern("f(1, ??, a=2, **{'b':3})")
        assert isinstance(pat.args, listmiddle)
        assert_ast_like(pat.args.front[0], ast.Num(n=1))
        assert not hasattr(pat, 'starargs')
        assert isinstance(pat.keywords, types.FunctionType)
        kwargs_dict = ast.Dict(keys=[ast.Str(s='b')], values=[ast.Num(n=3)])
        if sys.version_info < (3, 5):
            assert_ast_like(pat.kwargs, kwargs_dict)
        else:
            pat.keywords([ast.keyword(arg=None, value=kwargs_dict),
                          ast.keyword(arg='a', value=ast.Num(n=2))], [])

    def test_wildcard_funcdef(self):
        pat = prepare_pattern("def f(??): ??")
        assert_ast_like(pat, ast.FunctionDef(name='f'))
        assert isinstance(pat.args.args, listmiddle)
        assert pat.args.args.front == []
        assert pat.args.args.back == []
        assert not hasattr(pat.args.args, 'vararg')
        assert not hasattr(pat.args.args, 'kwonlyargs')
        assert not hasattr(pat.args.args, 'kwarg')

    def test_wildcard_funcdef_earlyargs(self):
        pat = prepare_pattern("def f(??, a): ??")
        assert isinstance(pat.args.args, listmiddle)
        assert_ast_like(pat.args.args.back[0], ast.arg(arg='a'))
        assert pat.args.vararg is must_not_exist_checker
        assert pat.args.kwonly_args_dflts == []

    def test_wildcard_funcdef_kwonlyargs(self):
        pat = prepare_pattern("def f(*, a, ??): ??")
        assert isinstance(pat.args, ArgsDefChecker)
        assert [a.arg for a,d in pat.args.kwonly_args_dflts] == ['a']
        assert pat.args.koa_subset
        assert pat.args.kwarg is None
        assert pat.args.args is must_not_exist_checker
        assert pat.args.vararg is must_not_exist_checker

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

class IterTestMixin:
    def assert_no_more(self, it):
        with self.assertRaises(StopIteration):
            next(it)

class PatternFinderTests(unittest.TestCase, IterTestMixin):
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

func_call_sample = """
f()
f(1)
f(1, 2)
f(1, 2, *c)
f(d=3)
f(d=3, e=4)
f(1, d=3, e=4)
f(1, d=4, **k)
"""

class FuncCallTests(unittest.TestCase, IterTestMixin):
    ast = ast.parse(func_call_sample)

    def test_wildcard_all(self):
        apf = ASTPatternFinder(prepare_pattern("f(??)"))
        matches = list(apf.scan_ast(self.ast))
        assert len(matches) == 8

    def test_pos_final_wildcard(self):
        apf = ASTPatternFinder(prepare_pattern("f(1, ??)"))
        it = apf.scan_ast(self.ast)
        assert_ast_like(next(it), ast.Call(args=[ast.Num(n=1)]))
        assert_ast_like(next(it), ast.Call(args=[ast.Num(n=1), ast.Num(n=2)]))
        assert_ast_like(next(it), ast.Call(starargs=ast.Name(id='c')))
        assert_ast_like(next(it), ast.Call(args=[ast.Num(n=1)],
                                         keywords=[ast.keyword(arg='d'),
                                                   ast.keyword(arg='e'),
                                                  ])
                       )
        assert_ast_like(next(it), ast.Call(kwargs=ast.Name(id='k')))
        self.assert_no_more(it)

    def test_pos_leading_wildcard(self):
        apf = ASTPatternFinder(prepare_pattern("f(??, 2)"))
        it = apf.scan_ast(self.ast)
        assert_ast_like(next(it), ast.Call(args=[ast.Num(n=1), ast.Num(n=2)]))
        self.assert_no_more(it)

    def test_keywords_wildcard(self):
        apf = ASTPatternFinder(prepare_pattern("f(e=4, ??=??)"))
        it = apf.scan_ast(self.ast)
        assert_ast_like(next(it), ast.Call(keywords=[ast.keyword(arg='d'),
                                                     ast.keyword(arg='e'),])
                        )
        self.assert_no_more(it)

    def test_keywords_wildcard2(self):
        apf = ASTPatternFinder(prepare_pattern("f(d=?, ??=??)"))
        matches = list(apf.scan_ast(self.ast))
        assert len(matches) == 2

    def test_mixed_wildcard(self):
        apf = ASTPatternFinder(prepare_pattern("f(??, d=?)"))
        matches = list(apf.scan_ast(self.ast))
        assert len(matches) == 4
        assert_ast_like(matches[-1], ast.Call(kwargs=ast.Name(id='k')))

    def test_single_and_multi_wildcard(self):
        apf = ASTPatternFinder(prepare_pattern("f(?, ??)"))
        matches = list(apf.scan_ast(self.ast))
        assert len(matches) == 5

func_def_samples = """
def f(): pass

def g(a): pass

def h(a, b): pass

def i(a, b, *, c): pass

def j(*a, c, d): pass

def k(a, b, **k): pass

def l(*, d, c, **k): pass

def m(a, b=2, c=4): pass

def n(a, b, c=4): pass
"""

class FuncDefTests(unittest.TestCase, IterTestMixin):
    ast = ast.parse(func_def_samples)

    def get_matching_names(self, pat):
        apf = ASTPatternFinder(prepare_pattern(pat))
        matches = apf.scan_ast(self.ast)
        return {f.name for f in matches}

    def test_wildcard_all(self):
        matches = self.get_matching_names("def ?(??): ??")
        assert matches == {'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n'}

    def test_trailing_wildcard(self):
        matches = self.get_matching_names("def ?(a, ??): ??")
        assert matches == {'g', 'h', 'i', 'k', 'm', 'n'}

    def test_wildcard_kwonlyargs(self):
        matches = self.get_matching_names("def ?(*, c, ??): ??")
        assert matches == {'l'}

    def test_wildcard_w_defaults(self):
        matches = self.get_matching_names("def ?(a, b=2, ??=??, c=4): ??")
        assert matches == {'m'}

    def test_wildcard_w_defaults2(self):
        matches = self.get_matching_names("def ?(a, b=2, ??=??): ??")
        assert matches == {'m'}

    def test_no_wildcard(self):
        matches = self.get_matching_names("def ?(a, b, c=4): ??")
        assert matches == {'m', 'n'}

    def test_mix_wildcards(self):
        matches = self.get_matching_names("def ?(?, ??): ??")
        assert matches == {'g', 'h', 'i', 'k', 'm', 'n'}
