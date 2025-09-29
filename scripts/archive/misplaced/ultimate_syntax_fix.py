#!/usr/bin/env python3
"""Ultimate comprehensive syntax fix to handle all remaining comma-related syntax errors."""

import re
from pathlib import Path


def fix_all_syntax_issues(file_path):
    """Fix all syntax issues caused by trailing commas in inappropriate places."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # 1. Fix trailing commas on lines that end with colons (if/for/while/try/def/class statements)
        # Pattern: if condition:, / for item in items:, / def function():, etc.
        content = re.sub(
            r"^(\s*(?:if|for|while|try|except|finally|def|class|with|elif|else)[^:\n]*):,(\s*)$",
            r"\1:\2",
            content,
            flags=re.MULTILINE,
        )

        # 2. Fix trailing commas on @abstractmethod decorator lines
        # Pattern: @abstractmethod,
        content = re.sub(r"^(\s*@\w+),(\s*)$", r"\1\2", content, flags=re.MULTILINE)

        # 3. Fix empty dictionaries/lists with trailing commas
        # Pattern: {, / [,
        content = re.sub(r"(\{\s*),(\s*)", r"\1\2", content)  # Empty dict
        content = re.sub(r"(\[\s*),(\s*)", r"\1\2", content)  # Empty list

        # 4. Fix function/method calls with trailing commas at end of line
        # Pattern: method(args):, or method(args),
        content = re.sub(r"^(\s*[^#\n]+\([^)]*\)):,(\s*)$", r"\1:\2", content, flags=re.MULTILINE)
        content = re.sub(r"^(\s*[^#\n]+\([^)]*\)),(\s*)$", r"\1\2", content, flags=re.MULTILINE)

        # 5. Fix assignment statements with trailing commas
        # Pattern: variable = value,
        content = re.sub(r"^(\s*[^#\n]+ = [^#\n]+),(\s*)$", r"\1\2", content, flags=re.MULTILINE)

        # 6. Fix return statements with trailing commas
        # Pattern: return value,
        content = re.sub(r"^(\s*return\s+[^#\n]+),(\s*)$", r"\1\2", content, flags=re.MULTILINE)

        # 7. Fix logger assignments specifically
        # Pattern: logger = get_logger(__name__),
        content = re.sub(r"^(\s*logger\s*=\s*[^#\n]+),(\s*)$", r"\1\2", content, flags=re.MULTILINE)

        # 8. Fix standalone trailing commas on any line that doesn't need them
        # Be very careful here - only remove trailing commas that are clearly wrong
        # This pattern looks for lines that end with comma but are not:
        # - Inside parentheses/brackets/braces that continue
        # - Part of tuple/list/dict definitions
        # - Import statements (already handled above)
        lines = content.split("\n")
        fixed_lines = []

        for i, line in enumerate(lines):
            # Skip if line doesn't end with comma
            if not line.rstrip().endswith(","):
                fixed_lines.append(line)
                continue

            # Check if this is a legitimate comma (inside a data structure)
            # Count open/close brackets to see if we're inside a structure
            open_parens = line.count("(") - line.count(")")
            open_brackets = line.count("[") - line.count("]")
            open_braces = line.count("{") - line.count("}")

            # If we have unmatched opening brackets, this comma might be legitimate
            if open_parens > 0 or open_brackets > 0 or open_braces > 0:
                # Check the next few lines to see if they close the structure
                legitimate_comma = False
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith("#"):
                        # If next line starts with closing bracket or continues the structure, keep comma
                        if next_line.startswith(("}", ")", "]")) or "," in next_line or next_line.endswith(","):
                            legitimate_comma = True
                            break
                        else:
                            break

                if legitimate_comma:
                    fixed_lines.append(line)
                    continue

            # Remove trailing comma from lines that clearly shouldn't have them
            stripped_line = line.rstrip()
            if stripped_line.endswith(","):
                # Check if this looks like a statement that shouldn't end with comma
                line_content = stripped_line[:-1].strip()  # Remove comma and whitespace

                # Patterns that should NOT end with comma:
                invalid_patterns = [
                    r":\s*$",  # Lines ending with colon (already handled above but extra safety)
                    r"^@\w+",  # Decorator lines
                    r"^\s*(if|for|while|try|except|finally|def|class|with|elif|else)\s",  # Control structures
                    r"^\s*return\s",  # Return statements
                    r"^\s*import\s",  # Import statements
                    r"^\s*from\s.*import\s",  # From-import statements
                    r"=\s*[^=]+$",  # Simple assignments (not dict/list definitions)
                ]

                should_remove_comma = any(re.search(pattern, line_content) for pattern in invalid_patterns)

                if should_remove_comma:
                    fixed_lines.append(line.rstrip()[:-1] + line[len(line.rstrip()) :])  # Keep original whitespace
                else:
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)

        content = "\n".join(fixed_lines)

        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Run ultimate syntax cleanup."""
    src_dir = Path("src")

    if not src_dir.exists():
        print("Error: src directory not found")
        return

    fixed_count = 0
    total_files = 0

    print("Running ultimate comprehensive syntax cleanup...")

    for py_file in src_dir.rglob("*.py"):
        total_files += 1
        if fix_all_syntax_issues(py_file):
            fixed_count += 1
            print(f"Fixed: {py_file}")

    print(f"Processed {total_files} files, fixed {fixed_count} files")


if __name__ == "__main__":
    main()
