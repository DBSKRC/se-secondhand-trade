"""Count application Python source without blank lines or docstrings."""

import ast
import pathlib
import tokenize


def count(path):
    """Return physical lines containing Python tokens outside docstrings."""
    with tokenize.open(path) as stream:
        text = stream.read()
    ignored = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef,
                             ast.AsyncFunctionDef)) and ast.get_docstring(node):
            doc = node.body[0]
            ignored.update(range(doc.lineno, doc.end_lineno + 1))
    omitted = {
        tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
        tokenize.COMMENT, tokenize.ENDMARKER,
    }
    with tokenize.open(path) as stream:
        tokens = tokenize.generate_tokens(stream.readline)
        lines = set()
        for token in tokens:
            if token.type not in omitted:
                lines.update(range(token.start[0], token.end[0] + 1))
    return len(lines - ignored)


def main():
    """Display per-file counts and check the lab threshold."""
    root = pathlib.Path(__file__).resolve().parents[1]
    total = 0
    for path in sorted((root / "campus").glob("*.py")):
        size = count(path)
        print(f"{path.name:20} {size:4}")
        total += size
    print(f"Application Python LOC: {total}")
    return 0 if total > 1500 else 1


if __name__ == "__main__":
    raise SystemExit(main())
