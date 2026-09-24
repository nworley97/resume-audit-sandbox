"""Portable syntax/project checks. This does not replace an Xcode build or UI tests.

Install tree-sitter==0.26.0 and tree-sitter-swift==0.7.3 in a temporary environment,
then run this script from any directory.
"""
from pathlib import Path
import re
import subprocess
import sys

from tree_sitter import Language, Parser
import tree_sitter_swift


def main():
    ios = Path(__file__).resolve().parents[1]
    parser = Parser(Language(tree_sitter_swift.language()))
    project = (ios / "AlteraSF.xcodeproj/project.pbxproj").read_text(encoding="utf-8-sig")
    failures = []
    baseline_limits = []
    sources = sorted((ios / "AlteraSF").rglob("*.swift"))
    for path in sources:
        source = path.read_bytes()
        tree = parser.parse(source)
        syntax_errors = []
        pending = [tree.root_node]
        while pending:
            node = pending.pop()
            if node.type == "ERROR" or node.is_missing:
                syntax_errors.append(f"{path.relative_to(ios)}:{node.start_point.row + 1}: {node.type}")
            pending.extend(node.children)
        if syntax_errors:
            baseline = subprocess.run(
                ["git", "show", f"HEAD:{path.relative_to(ios.parent).as_posix()}"],
                cwd=ios.parent, capture_output=True, check=False,
            )
            # Only untouched files may be classified as baseline parser limits.
            if baseline.returncode == 0 and baseline.stdout.replace(b"\r\n", b"\n") == source.replace(b"\r\n", b"\n"):
                baseline_limits.extend(syntax_errors)
            else:
                failures.extend(syntax_errors)
        # Each source must be declared and included in the Sources build phase.
        pattern = rf"/\* {re.escape(path.name)} in Sources \*/"
        if len(re.findall(pattern, project)) != 2:
            failures.append(f"{path.name}: expected one build-file declaration and one Sources entry")
    if failures:
        print("\n".join(failures))
        return 1
    if baseline_limits:
        print("Untouched HEAD files with existing parser diagnostics (not validated):")
        print("\n".join(baseline_limits))
    print(f"PASS: no syntax diagnostics in modified Swift files; all {len(sources)} sources are included in the Xcode project.")
    print("Not checked: Swift type checking, SDK availability, runtime behavior, or rendered layout.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
