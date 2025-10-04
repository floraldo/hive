"""Simple demo of E2E Tester Agent Phase 2 capabilities.

This script demonstrates:
1. Parsing a feature description into test scenario
2. Generating E2E test code from scenario
3. Showing the generated test (execution requires browser setup)
"""

from pathlib import Path

from src.e2e_tester import ScenarioParser, TestGenerator


def main():
    """Run E2E Tester Agent demo."""
    print("=" * 80)
    print("E2E TESTER AGENT - PHASE 2 DEMO")
    print("=" * 80)
    print()

    # Feature description
    feature = "User can login with Google OAuth"
    url = "https://myapp.dev/login"

    print(f"Feature: {feature}")
    print(f"URL: {url}")
    print()

    # Step 1: Parse scenario
    print("-" * 80)
    print("STEP 1: SCENARIO PARSING")
    print("-" * 80)

    parser = ScenarioParser()
    scenario = parser.parse(
        feature=feature,
        url=url,
        additional_context={
            "success_indicator": "User dashboard visible",
            "failure_indicator": "Error message displayed",
        }
    )

    print("[OK] Parsed scenario:")
    print(f"   Feature name: {scenario.feature_name}")
    print(f"   Actions: {len(scenario.actions)}")
    print(f"   Success assertions: {len(scenario.success_assertions)}")
    print(f"   Page elements: {len(scenario.page_elements)}")
    print()

    # Show parsed data
    print("Actions:")
    for i, action in enumerate(scenario.actions, 1):
        print(f"   {i}. {action['type']}: {action['target']}")
    print()

    print("Page Elements:")
    for name, selector in scenario.page_elements.items():
        print(f"   - {name}: {selector}")
    print()

    # Step 2: Generate test
    print("-" * 80)
    print("STEP 2: TEST GENERATION")
    print("-" * 80)

    generator = TestGenerator()
    generated = generator.generate_test(
        feature=feature,
        url=url,
        additional_context={
            "success_indicator": "User dashboard visible",
            "failure_indicator": "Error message displayed",
        }
    )

    print("[OK] Generated test:")
    print(f"   Test name: {generated.test_name}")
    print(f"   Lines of code: {len(generated.test_code.splitlines())}")
    print(f"   Generated at: {generated.generated_at}")
    print()

    # Step 3: Show generated code (first 50 lines)
    print("-" * 80)
    print("STEP 3: GENERATED TEST CODE (preview)")
    print("-" * 80)
    print()

    lines = generated.test_code.splitlines()
    preview_lines = lines[:50]

    for line in preview_lines:
        print(line)

    if len(lines) > 50:
        print(f"\n... ({len(lines) - 50} more lines)")

    print()

    # Step 4: Save to file (optional)
    output_path = Path("tests/e2e/test_google_login_demo.py")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generated.test_code, encoding="utf-8")

    print("-" * 80)
    print("COMPLETE")
    print("-" * 80)
    print(f"[OK] Test saved to: {output_path}")
    print()
    print("To execute the generated test:")
    print(f"  python -m pytest {output_path} -v")
    print()
    print("Note: Requires Playwright browser installation:")
    print("  python -m playwright install chromium")
    print()


if __name__ == "__main__":
    main()
