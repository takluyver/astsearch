import ast
from io import StringIO
import types
import unittest

import pytest

from astcheck import assert_ast_like, listmiddle, name_or_attr
from astsearch import (
    prepare_pattern, ASTPatternFinder, must_exist_checker, must_not_exist_checker,
    ArgsDefChecker,
)

def assert_iterator_finished(it):
    with pytest.raises(StopIteration):
        next(it)

def get_matches(pattern, sample_code):
    sample_ast = ast.parse(sample_code)
    print(ast.dump(sample_ast))
    return list(ASTPatternFinder(pattern).scan_ast(sample_ast))


# Tests of just preparing the pattern --------------------------------

def test_prepare_plain():
    pat = prepare_pattern('1/2')
    assert_ast_like(pat, ast.BinOp(
        left=ast.Constant(1), op=ast.Div(), right=ast.Constant(2)
    ))

def test_simple_wildcard():
    pat = prepare_pattern('?/?')
    assert_ast_like(pat, ast.BinOp(op=ast.Div()))
    assert pat.left is must_exist_checker
    assert pat.right is must_exist_checker

def test_wildcard_body():
    pat = prepare_pattern('if True: ??\nelse: ??')
    assert isinstance(pat, ast.If)
    assert pat.body is must_exist_checker
    assert pat.orelse is must_exist_checker

    pat2 = prepare_pattern('if True: ??')
    assert isinstance(pat2, ast.If)
    assert pat.body is must_exist_checker
    assert not hasattr(pat2, 'orelse')

def test_wildcard_body_part():
    pat = prepare_pattern("def foo():\n  ??\n  return a")
    assert isinstance(pat, ast.FunctionDef)
    assert isinstance(pat.body, listmiddle)
    assert_ast_like(pat.body.back[0], ast.Return(ast.Name(id='a')))

def test_name_or_attr():
    pat = prepare_pattern('a = 1')
    assert_ast_like(pat, ast.Assign(value=ast.Constant(1)))
    assert isinstance(pat.targets[0], name_or_attr)

def test_wildcard_call_args():
    pat = prepare_pattern("f(??)")
    assert isinstance(pat, ast.Call)
    assert isinstance(pat.args, listmiddle)
    assert pat.args.front == []
    assert pat.args.back == []
    assert not hasattr(pat, 'keywords')

def test_wildcard_some_call_args():
    pat = prepare_pattern("f(??, 1)")
    assert isinstance(pat.args, listmiddle)
    assert pat.args.front == []
    assert_ast_like(pat.args.back[0], ast.Constant(1))
    assert pat.keywords == must_not_exist_checker

def test_wildcard_call_keywords():
    pat = prepare_pattern("f(a=1, ??=??)")
    assert pat.args == must_not_exist_checker
    assert isinstance(pat.keywords, types.FunctionType)

def test_wildcard_call_mixed_args():
    pat = prepare_pattern("f(1, ??, a=2, **{'b':3})")
    assert isinstance(pat.args, listmiddle)
    assert_ast_like(pat.args.front[0], ast.Constant(1))
    assert isinstance(pat.keywords, types.FunctionType)
    kwargs_dict = ast.Dict(keys=[ast.Constant('b')], values=[ast.Constant(3)])
    pat.keywords([ast.keyword(arg=None, value=kwargs_dict),
                  ast.keyword(arg='a', value=ast.Constant(2))], [])

def test_wildcard_funcdef():
    pat = prepare_pattern("def f(??): ??")
    assert_ast_like(pat, ast.FunctionDef(name='f'))
    assert isinstance(pat.args.args, listmiddle)
    assert pat.args.args.front == []
    assert pat.args.args.back == []
    assert not hasattr(pat.args.args, 'vararg')
    assert not hasattr(pat.args.args, 'kwonlyargs')
    assert not hasattr(pat.args.args, 'kwarg')

def test_wildcard_funcdef_earlyargs():
    pat = prepare_pattern("def f(??, a): ??")
    assert isinstance(pat.args.args, listmiddle)
    assert_ast_like(pat.args.args.back[0], ast.arg(arg='a'))
    assert pat.args.vararg is must_not_exist_checker
    assert pat.args.kwonly_args_dflts == []

def test_wildcard_funcdef_kwonlyargs():
    pat = prepare_pattern("def f(*, a, ??): ??")
    assert isinstance(pat.args, ArgsDefChecker)
    assert [a.arg for a,d in pat.args.kwonly_args_dflts] == ['a']
    assert pat.args.koa_subset
    assert pat.args.kwarg is None
    assert pat.args.args is must_not_exist_checker
    assert pat.args.vararg is must_not_exist_checker

def test_attr_no_ctx():
    pat = prepare_pattern('?.baz')
    assert_ast_like(pat, ast.Attribute(attr='baz'))
    assert not hasattr(pat, 'ctx')
    matches = get_matches(pat, 'foo.baz = 1')
    assert len(matches) == 1

def test_subscript_no_ctx():
    pat = prepare_pattern('?[2]')
    assert_ast_like(pat, ast.Subscript(slice=ast.Index(value=ast.Constant(2))))
    assert not hasattr(pat, 'ctx')
    matches = get_matches(pat, 'd[2] = 1')
    assert len(matches) == 1

def test_import():
    pat = prepare_pattern("import ?")
    assert isinstance(pat, ast.Import)
    assert len(pat.names) == 1
    assert pat.names[0].name is must_exist_checker

def test_import_multi():
    pat = prepare_pattern("import ??")
    assert isinstance(pat, ast.Import)
    assert not hasattr(pat, 'names')

    pat = prepare_pattern("from x import ??")
    assert isinstance(pat, ast.ImportFrom)
    assert pat.module == 'x'
    assert not hasattr(pat, 'names')

def test_import_from():
    pat = prepare_pattern("from ? import ?")
    print(ast.dump(pat, indent=2))
    assert isinstance(pat, ast.ImportFrom)
    assert pat.module is must_exist_checker
    assert len(pat.names) == 1
    assert pat.names[0].name is must_exist_checker
    assert len(get_matches(pat, "from foo import bar as foobar")) == 1

def test_string_u_prefix():
    pat = prepare_pattern('"foo"')
    assert len(get_matches(pat, "u'foo'")) == 1

def test_bare_except():
    pat = prepare_pattern("try: ??\nexcept: ??")
    print(ast.dump(pat, indent=2))
    assert len(get_matches(pat, "try: pass\nexcept: pass")) == 1
    # 'except:' should only match a bare assert with no exception type
    assert len(get_matches(pat, "try: pass\nexcept Exception: pass")) == 0


# Tests of general matching -----------------------------------------------

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

def test_match_plain():
    pat = ast.BinOp(left=ast.Constant(1), right=ast.Constant(2), op=ast.Div())
    it = ASTPatternFinder(pat).scan_file(StringIO(division_sample))
    assert next(it).left.value == 1
    assert_iterator_finished(it)

def test_all_divisions():
    pat = ast.BinOp(op=ast.Div())
    it = ASTPatternFinder(pat).scan_file(StringIO(division_sample))
    assert_ast_like(next(it), ast.BinOp(left=ast.Constant(1)))
    assert_ast_like(next(it), ast.BinOp(right=ast.Name(id='c')))
    assert_ast_like(next(it), ast.BinOp(left=ast.Name(id='x')))
    assert_iterator_finished(it)

def test_block_must_exist():
    pat = ast.If(orelse=must_exist_checker)
    it = ASTPatternFinder(pat).scan_file(StringIO(if_sample))
    assert_ast_like(next(it), ast.If(test=ast.Name(id='a')))
    assert_iterator_finished(it)


# Test matching of function calls -----------------------------------

func_call_sample = """
f1()
f2(1)
f3(1, 2)
f4(1, 2, *c)
f5(d=3)
f6(d=3, e=4)
f7(1, d=3, e=4)
f8(1, d=4, **k)
"""

class FuncCallTests(unittest.TestCase):
    ast = ast.parse(func_call_sample)

    def get_matching_names(self, pat):
        apf = ASTPatternFinder(prepare_pattern(pat))
        matches = apf.scan_ast(self.ast)
        return [f.func.id for f in matches]

    def test_wildcard_all(self):
        assert self.get_matching_names("?(??)") == [f"f{i}" for i in range(1, 9)]

    def test_pos_final_wildcard(self):
        assert self.get_matching_names("?(1, ??)") == ["f2", "f3", "f4", "f7", "f8"]

    def test_pos_leading_wildcard(self):
        assert self.get_matching_names("?(??, 2)") == ["f3"]

    def test_keywords_wildcard(self):
        assert self.get_matching_names("?(e=4, ??=??)") == ["f6"]

    def test_keywords_wildcard2(self):
        assert self.get_matching_names("?(d=?, ??=??)") == ["f5", "f6"]

    def test_mixed_wildcard(self):
        assert self.get_matching_names("?(??, d=?)") == ["f5", "f6", "f7", "f8"]

    def test_single_and_multi_wildcard(self):
        assert self.get_matching_names("?(?, ??)") == ["f2", "f3", "f4", "f7", "f8"]

# Test matching of function definitions ---------------------------------

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

class FuncDefTests(unittest.TestCase):
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
