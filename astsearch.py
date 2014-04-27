import astcheck, ast
import os.path
import warnings

class ASTPatternFinder(object):
    """Scans Python code for AST nodes matching pattern.
    
    :param ast.AST pattern: The node pattern to search for
    """
    def __init__(self, pattern):
        self.pattern = pattern

    def scan_ast(self, tree):
        """Walk an AST and yield nodes matching pattern.
        
        :param ast.AST pattern: The node pattern to search for
        :param ast.AST tree: The AST in which to search
        """
        nodetype = type(self.pattern)
        for node in ast.walk(tree):
            if isinstance(node, nodetype) and astcheck.is_ast_like(node, self.pattern):
                yield node

    def scan_file(self, filename):
        """Parse a file and yield AST nodes matching pattern.
        
        :param str filename: Path to a Python file
        """
        with open(filename, 'rb') as f:
            tree = ast.parse(f.read())
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


WILDCARD_NAME = "__astsearch_wildcard"

class TemplatePruner(ast.NodeTransformer):
    def visit_Name(self, node):
        if node.id == WILDCARD_NAME:
            return None  # Remove node to allow any object
        
        # Generalise names to allow attributes as well, because these are often
        # interchangeable.
        return astcheck.name_or_attr(node.id)
    
    def prune_wildcard(self, node, attrname):
        if getattr(node, attrname, None) == WILDCARD_NAME:
            delattr(node, attrname)

    def visit_Attribute(self, node):
        self.prune_wildcard(node, 'attr')
        return self.generic_visit(node)

    def visit_keyword(self, node):
        self.prune_wildcard(node, 'arg')
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.prune_wildcard(node, 'name')
        return self.generic_visit(node)

    def visit_arg(self, node):
        self.prune_wildcard(node, 'arg')
        return self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.prune_wildcard(node, 'name')
        return self.generic_visit(node)

    def generic_visit(self, node):
        # Copied from ast.NodeTransformer; changes marked PATCH
        for field, old_value in ast.iter_fields(node):
            old_value = getattr(node, field, None)
            if isinstance(old_value, list):
                new_values = []
                # PATCH: If wildcard is whole body of function/loop/etc,
                # don't check the block at all.
                if len(old_value) == 1 and isinstance(old_value[0], ast.AST) \
                        and astcheck.is_ast_like(old_value[0],
                             ast.Expr(value=ast.Name(id=WILDCARD_NAME))):
                    pass
                # -----------
                else:
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
    s = s.replace('?', WILDCARD_NAME)
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
    
    current_filepath = None
    current_filelines = []
    for filepath, node in ASTPatternFinder(ast_pattern).scan_directory(args.path):
        if filepath != current_filepath:
            with open(filepath, 'r') as f:  # TODO: detect encoding
                current_filelines = f.readlines()
            if current_filepath is not None:
                print()  # Blank line between files
            current_filepath = filepath
            print(filepath)
        print("{:>4}|{}".format(node.lineno, current_filelines[node.lineno-1].rstrip()))

if __name__ == '__main__':
    main()