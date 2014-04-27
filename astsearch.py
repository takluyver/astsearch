import astcheck, ast
import os.path
import warnings

def scan_ast(pattern, tree):
    nodetype = type(pattern)
    for node in ast.walk(tree):
        if isinstance(node, nodetype) and astcheck.is_ast_like(node, pattern):
            yield node

def scan_file(pattern, filename):
    with open(filename, 'rb') as f:
        tree = ast.parse(f.read())
    yield from scan_ast(pattern, tree)

def scan_directory(pattern, directory):
    for dirpath, dirnames, filenames in os.walk(directory):
        for filename in filenames:
            if filename.endswith(('.py', '.pyw')):
                filepath = os.path.join(dirpath, filename)
                try:
                    for match in scan_file(pattern, filepath):
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
    
    def visit_Attribute(self, node):
        if node.attr == WILDCARD_NAME:
            del node.attr
        return node

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
                        # PATCH: We want to put functions in the AST
                        elif isinstance(value, list): #not isinstance(value, ast.AST):
                            new_values.extend(value)
                            continue
                    new_values.append(value)
                # PATCH: Delete field if list is empty
                if not new_values:
                    delattr(node, field)
                old_value[:] = new_values
            elif isinstance(old_value, ast.AST):
                new_node = self.visit(old_value)
                if new_node is None:
                    delattr(node, field)
                else:
                    setattr(node, field, new_node)
        return node

def prepare_pattern(s):
    s = s.replace('?', WILDCARD_NAME)
    pattern = ast.parse(s).body[0]
    if isinstance(pattern, ast.Expr):
        pattern = pattern.value
    return TemplatePruner().visit(pattern)

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('pattern')
    ap.add_argument('--debug', action='store_true')
    
    args = ap.parse_args(argv)
    ast_pattern = prepare_pattern(args.pattern)
    if args.debug:
        print(ast.dump(ast_pattern))
    
    current_filepath = None
    current_filelines = []
    for filepath, node in scan_directory(ast_pattern, '.'):
        if filepath != current_filepath:
            with open(filepath, 'r') as f:  # TODO: detect encoding
                current_filelines = f.readlines()
            current_filepath = filepath
            print(filepath)
        print("{:>4}:{}".format(node.lineno, current_filelines[node.lineno-1].rstrip()))

if __name__ == '__main__':
    main()