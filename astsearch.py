import astcheck, ast
import os.path
import sys
import warnings

class ASTPatternFinder(object):
    """Scans Python code for AST nodes matching pattern.
    
    :param ast.AST pattern: The node pattern to search for
    """
    def __init__(self, pattern):
        self.pattern = pattern

    def scan_ast(self, tree):
        """Walk an AST and yield nodes matching pattern.
        
        :param ast.AST tree: The AST in which to search
        """
        nodetype = type(self.pattern)
        for node in ast.walk(tree):
            if isinstance(node, nodetype) and astcheck.is_ast_like(node, self.pattern):
                yield node

    def scan_file(self, file):
        """Parse a file and yield AST nodes matching pattern.
        
        :param file: Path to a Python file, or a readable file object
        """
        if isinstance(file, str):
            with open(file, 'rb') as f:
                tree = ast.parse(f.read())
        else:
            tree = ast.parse(file.read())
        yield from self.scan_ast(tree)
    
    def filter_subdirs(self, dirnames):
        dirnames[:] = [d for d in dirnames if d != 'build']

    def scan_directory(self, directory):
        """Walk files in a directory, yielding (filename, node) pairs matching
        pattern.
        
        :param str directory: Path to a directory to search
        
        Only files with a ``.py`` or ``.pyw`` extension will be scanned.
        """
        for dirpath, dirnames, filenames in os.walk(directory):
            self.filter_subdirs(dirnames)

            for filename in filenames:
                if filename.endswith(('.py', '.pyw')):
                    filepath = os.path.join(dirpath, filename)
                    try:
                        for match in self.scan_file(filepath):
                            yield filepath, match
                    except SyntaxError as e:
                        warnings.warn("Failed to parse {}:\n{}".format(filepath, e))

def must_exist_checker(node, path):
    """Checker function to ensure a field is not empty"""
    if (node is None) or (node == []):
        raise astcheck.ASTMismatch(path, node, "non empty")

def must_not_exist_checker(node, path):
    """Checker function to ensure a field is empty"""
    if (node is not None) and (node != []):
        raise astcheck.ASTMismatch(path, node, "empty")

WILDCARD_NAME = "__astsearch_wildcard"
MULTIWILDCARD_NAME = "__astsearch_multiwildcard"

class TemplatePruner(ast.NodeTransformer):
    def visit_Name(self, node):
        if node.id == WILDCARD_NAME:
            return must_exist_checker  # Allow any node type for a wildcard
        elif node.id == MULTIWILDCARD_NAME:
            # This shouldn't happen, but users will probably confuse their
            # wildcards at times. If it's in a block, it should have been
            # transformed before it's visited.
            return must_exist_checker
        
        # Generalise names to allow attributes as well, because these are often
        # interchangeable.
        return astcheck.name_or_attr(node.id)
    
    def prune_wildcard(self, node, attrname, must_exist=False):
        """Prunes a plain string attribute if it matches WILDCARD_NAME"""
        if getattr(node, attrname, None) in (WILDCARD_NAME, MULTIWILDCARD_NAME):
            setattr(node, attrname, must_exist_checker)

    def prune_wildcard_body(self, node, attrname, must_exist=False):
        """Prunes a code block (e.g. function body) if it is a wildcard"""
        body = getattr(node, attrname, [])
        def _is_multiwildcard(n):
            return astcheck.is_ast_like(n,
                            ast.Expr(value=ast.Name(id=MULTIWILDCARD_NAME)))

        if len(body) == 1 and _is_multiwildcard(body[0]):
            setattr(node, attrname, must_exist_checker)
            return

        # Find a ?? node within the block, and replace it with listmiddle
        for i, n in enumerate(body):
            if _is_multiwildcard(n):
                newbody = body[:i] + astcheck.listmiddle() + body[i+1:]
                setattr(node, attrname, newbody)

    def visit_Attribute(self, node):
        self.prune_wildcard(node, 'attr')
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.prune_wildcard(node, 'name')
        self.prune_wildcard_body(node, 'body')
        return self.generic_visit(node)

    visit_ClassDef = visit_FunctionDef

    def visit_arg(self, node):
        self.prune_wildcard(node, 'arg')
        return self.generic_visit(node)

    def visit_If(self, node):
        self.prune_wildcard_body(node, 'body')
        self.prune_wildcard_body(node, 'orelse')
        return self.generic_visit(node)

    # All of these have body & orelse node lists
    visit_For = visit_While = visit_If

    def visit_Try(self, node):
        self.prune_wildcard_body(node, 'body')
        self.prune_wildcard_body(node, 'orelse')
        self.prune_wildcard_body(node, 'finalbody')
        return self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        self.prune_wildcard(node, 'name')
        self.prune_wildcard_body(node, 'body')
        return self.generic_visit(node)

    def visit_With(self, node):
        self.prune_wildcard_body(node, 'body')
        return self.generic_visit(node)

    def visit_Call(self, node):
        positional_final_wildcard = False
        for i, n in enumerate(node.args):
            if astcheck.is_ast_like(n, ast.Name(id=MULTIWILDCARD_NAME)):
                if i+1 == len(node.args):
                    # Last positional argument - wildcard may extend to kwargs
                    positional_final_wildcard = True

                node.args = node.args[:i] + astcheck.listmiddle() + node.args[i+1:]

                # Don't try to handle multiple multiwildcards
                break

        kwargs_are_subset = False
        if positional_final_wildcard and node.starargs is None:
            del node.starargs   # Accept any (or none) *args
            # f(a, ??) -> wildcarded kwargs as well
            kwargs_are_subset = True

        if kwargs_are_subset or any(k.arg==MULTIWILDCARD_NAME for k in node.keywords):
            template_keywords = [self.visit(k) for k in node.keywords
                                  if k.arg != MULTIWILDCARD_NAME]

            def kwargs_checker(sample_keywords, path):
                sample_kwargs = {k.arg: k.value for k in sample_keywords}

                for k in template_keywords:
                    if k.arg == MULTIWILDCARD_NAME:
                        continue
                    if k.arg in sample_kwargs:
                        print(k.value, sample_kwargs[k.arg])
                        print('checking kw value', k.arg, astcheck.is_ast_like(sample_kwargs[k.arg], k.value))
                        astcheck.assert_ast_like(sample_kwargs[k.arg], k.value, path+[k.arg])
                    else:
                        print('missing kw', k.arg)
                        raise astcheck.ASTMismatch(path, '(missing)', 'keyword arg %s' % k.arg)

            if template_keywords:
                node.keywords = kwargs_checker
            else:
                # Shortcut if there are no keywords to check
                del node.keywords

            # Accepting arbitrary keywords, so don't check absence of **kwargs
            if node.kwargs is None:
                del node.kwargs

        # In block contexts, we want to avoid checking empty lists (for optional
        # nodes), but here, an empty list should mean that there are no
        # arguments in that group. So we need to override the behaviour in
        # generic_visit
        if node.args == []:
            node.args = must_not_exist_checker
        if getattr(node, 'keywords', None) == []:
            node.keywords = must_not_exist_checker
        return self.generic_visit(node)

    def generic_visit(self, node):
        # Copied from ast.NodeTransformer; changes marked PATCH
        for field, old_value in ast.iter_fields(node):
            old_value = getattr(node, field, None)
            if isinstance(old_value, list):
                new_values = []
                for value in old_value:
                    if isinstance(value, ast.AST):
                        value = self.visit(value)
                        if value is None:
                            continue
                        # PATCH: We want to put checker functions in the AST
                        #elif not isinstance(value, ast.AST):
                        elif isinstance(value, list):
                            # -------
                            new_values.extend(value)
                            continue
                    new_values.append(value)
                # PATCH: Delete field if list is empty
                if not new_values:
                    delattr(node, field)
                # ------
                old_value[:] = new_values
            elif isinstance(old_value, ast.AST):
                new_node = self.visit(old_value)
                if new_node is None:
                    delattr(node, field)
                else:
                    setattr(node, field, new_node)
        return node

def prepare_pattern(s):
    """Turn a string pattern into an AST pattern
    
    This parses the string to an AST, and generalises it a bit for sensible
    matching. ``?`` is treated as a wildcard that matches anything. Names in
    the pattern will match names or attribute access (i.e. ``foo`` will match
    ``bar.foo`` in files).
    """
    s = s.replace('??', MULTIWILDCARD_NAME).replace('?', WILDCARD_NAME)
    pattern = ast.parse(s).body[0]
    if isinstance(pattern, ast.Expr):
        pattern = pattern.value
    return TemplatePruner().visit(pattern)

def main(argv=None):
    """Run astsearch from the command line.
    
    :param list argv: Command line arguments; defaults to :data:`sys.argv`
    """
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('pattern',
                    help="AST pattern to search for; see docs for examples")
    ap.add_argument('path', nargs='?', default='.',
                    help="file or directory to search in")
    ap.add_argument('--debug', action='store_true', help=argparse.SUPPRESS)
    
    args = ap.parse_args(argv)
    ast_pattern = prepare_pattern(args.pattern)
    if args.debug:
        print(ast.dump(ast_pattern))
    
    patternfinder = ASTPatternFinder(ast_pattern)

    def _printline(node, filelines):
        print("{:>4}|{}".format(node.lineno, filelines[node.lineno-1].rstrip()))

    current_filelines = []
    if os.path.isdir(args.path):
        # Search directory
        current_filepath = None
        for filepath, node in patternfinder.scan_directory(args.path):
            if filepath != current_filepath:
                with open(filepath, 'r') as f:  # TODO: detect encoding
                    current_filelines = f.readlines()
                if current_filepath is not None:
                    print()  # Blank line between files
                current_filepath = filepath
                print(filepath)
            _printline(node, current_filelines)

    elif os.path.exists(args.path):
        # Search file
        for node in patternfinder.scan_file(args.path):
            if not current_filelines:
                with open(args.path) as f:
                    current_filelines = f.readlines()
            _printline(node, current_filelines)

    else:
        sys.exit("No such file or directory: {}".format(args.path))

if __name__ == '__main__':
    main()