"""Fix remaining syntax errors from over-aggressive comma fixing."""

from pathlib import Path


def fix_content(content: str) -> tuple[str, list[str]]:
    """Fix syntax errors in content."""
    issues = ([],)

    lines = (content.split("\n"),)
    fixed_lines = []

    for line in lines:
        stripped = line.strip()

        # Pattern: if foo:, -> if foo:
        if stripped and (stripped.endswith(":,") or stripped.endswith(": ,")):
            line = line.rstrip().rstrip(",")
            if "Fixed trailing comma after colon" not in issues:
                issues.append("Fixed trailing comma after colon")

        # Pattern: comment with comma: # comment,
        if "#" in line:
            before_comment, comment = line.split("#", 1)
            if comment.rstrip().endswith(","):
                comment = comment.rstrip().rstrip(",")
                line = before_comment + "#" + comment
                if "Fixed trailing comma in comment" not in issues:
                    issues.append("Fixed trailing comma in comment")

        fixed_lines.append(line)

    content = "\n".join(fixed_lines)
    return content, issues


def process_file(file_path: Path) -> tuple[bool, list[str]]:
    """Process a single file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        fixed_content, issues = fix_content(content)

        if fixed_content != content:
            file_path.write_text(fixed_content, encoding="utf-8")
            return True, issues

        return False, []
    except Exception as e:
        return False, [f"ERROR: {e}"]


def main():
    """Main execution."""
    src_dir = Path(__file__).parent.parent / "src" / "ecosystemiser"

    if not src_dir.exists():
        print(f"ERROR: Source directory not found: {src_dir}")
        return

    print("Fixing remaining syntax errors...")

    fixed_files = []

    for py_file in src_dir.rglob("*.py"):
        modified, issues = process_file(py_file)
        if modified:
            fixed_files.append((py_file.relative_to(src_dir), issues))
            print(f"  FIXED: {py_file.relative_to(src_dir)}")
            for issue in issues:
                print(f"    - {issue}")

    print(f"\nCompleted: {len(fixed_files)} files fixed")


if __name__ == "__main__":
    main()
