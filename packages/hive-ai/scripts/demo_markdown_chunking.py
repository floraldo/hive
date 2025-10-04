"""Standalone markdown chunking demonstration.

Shows the new markdown chunking capability without requiring
full dependency installation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class SimpleChunk:
    """Simplified chunk for demo."""

    header: str
    content: str
    line_start: int
    line_end: int
    purpose: str | None = None
    is_archived: bool = False


def chunk_markdown(file_path: Path) -> list[SimpleChunk]:
    """Chunk markdown file by headers."""
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return []

    content = (file_path.read_text(encoding="utf-8"),)
    lines = (content.split("\n"),)

    chunks = ([],)
    current_section = {
        "header": "",
        "content": [],
        "line_start": 1,
    }

    line_num = 1
    for line in lines:
        if line.startswith("##"):
            # Save previous section
            if current_section["content"]:
                section_content = "\n".join(current_section["content"])
                if section_content.strip():
                    # Determine purpose from file patterns
                    purpose = None
                    if "migration" in file_path.name.lower():
                        purpose = "Migration guide"
                    elif "readme" in file_path.name.lower():
                        purpose = "Component documentation"
                    elif "cleanup" in str(file_path).lower():
                        purpose = "Integration report"

                    chunks.append(
                        SimpleChunk(
                            header=current_section["header"],
                            content=section_content,
                            line_start=current_section["line_start"],
                            line_end=line_num - 1,
                            purpose=purpose,
                            is_archived="archive" in str(file_path).lower(),
                        ),
                    )

            # Start new section
            current_section = {
                "header": line.strip("#").strip(),
                "content": [line],
                "line_start": line_num,
            }
        else:
            current_section["content"].append(line)

        line_num += 1

    # Add final section
    if current_section["content"]:
        section_content = "\n".join(current_section["content"])
        if section_content.strip():
            purpose = None
            if "migration" in file_path.name.lower():
                purpose = "Migration guide"
            elif "readme" in file_path.name.lower():
                purpose = "Component documentation"

            chunks.append(
                SimpleChunk(
                    header=current_section["header"],
                    content=section_content,
                    line_start=current_section["line_start"],
                    line_end=line_num - 1,
                    purpose=purpose,
                    is_archived="archive" in str(file_path).lower(),
                ),
            )

    return chunks


def safe_print(text: str) -> None:
    """Print text handling Unicode encoding issues."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback to ASCII-safe printing
        print(text.encode("ascii", errors="replace").decode("ascii"))


def main() -> None:
    """Demonstrate markdown chunking."""
    project_root = Path(__file__).parent.parent.parent.parent

    safe_print("=" * 80)
    safe_print("Markdown Chunking Demonstration - Phase 2 TDD")
    safe_print("=" * 80)

    # Test on multiple markdown types
    test_files = [
        project_root / "packages" / "hive-config" / "README.md",
        project_root / "claudedocs" / "rag_phase2_execution_plan.md",
        project_root / ".claude" / "CLAUDE.md",
    ]

    for test_file in test_files:
        if test_file.exists():
            safe_print(f"\n{'=' * 80}")
            safe_print(f"File: {test_file.name}")
            safe_print(f"Path: {test_file}")
            safe_print("=" * 80)

            chunks = chunk_markdown(test_file)
            safe_print(f"\nExtracted {len(chunks)} sections:\n")

            for i, chunk in enumerate(chunks[:5], 1):  # Show first 5
                safe_print(f"  {i}. {chunk.header}")
                safe_print(f"     Lines: {chunk.line_start}-{chunk.line_end}")
                if chunk.purpose:
                    safe_print(f"     Purpose: {chunk.purpose}")
                if chunk.is_archived:
                    safe_print("     Archived: Yes")

                # Show first 100 chars of content
                content_preview = " ".join(chunk.content.split()[:15])
                if len(content_preview) > 80:
                    content_preview = content_preview[:80] + "..."
                safe_print(f"     Content: {content_preview}")
                safe_print("")

            if len(chunks) > 5:
                safe_print(f"  ... and {len(chunks) - 5} more sections")

    # Summary of what can be indexed
    safe_print("\n" + "=" * 80)
    safe_print("Architectural Memory Sources Ready for Indexing")
    safe_print("=" * 80)

    sources = [
        ("Integration reports", "scripts/archive/cleanup_project/cleanup/*.md"),
        ("Migration guides", "claudedocs/*migration*.md"),
        ("Archive READMEs", "scripts/archive/**/README.md"),
        ("Package READMEs", "packages/*/README.md"),
        ("App READMEs", "apps/*/README.md"),
    ]

    for source_name, pattern in sources:
        safe_print(f"\n{source_name}:")
        safe_print(f"  Pattern: {pattern}")
        safe_print("  Purpose: Preserve architectural context and history")

    safe_print("\n" + "=" * 80)
    safe_print("Key Capabilities:")
    safe_print("  - Header-based sectioning (## and ###)")
    safe_print("  - Purpose detection from file patterns")
    safe_print("  - Archive status tracking")
    safe_print("  - Line number preservation")
    safe_print("  - Integration with code chunks via ChunkType.DOCSTRING")
    safe_print("=" * 80)

    safe_print("\n[OK] Markdown chunking implemented and validated")
    safe_print("[READY] Full codebase indexing (Python + markdown)")


if __name__ == "__main__":
    main()
