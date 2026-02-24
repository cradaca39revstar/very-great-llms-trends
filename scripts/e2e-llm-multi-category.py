#!/usr/bin/env python3
"""
E2E test for LLM report across multiple L2 categories.
Calls e2e-llm-report.py for each category. For categories with data expect success;
for the empty category expect exit code 1 (no products).

Usage:
  python scripts/e2e-llm-multi-category.py
  python scripts/e2e-llm-multi-category.py --categories "Skincare" "Makeup" "Haircare & Styling"
  python scripts/e2e-llm-multi-category.py --empty-category "Eye & Ear Care"
"""

import argparse
import os
import subprocess
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(script_dir)
E2E_SCRIPT = os.path.join(script_dir, "e2e-llm-report.py")

# Default: categories that should have data (success)
DEFAULT_CATEGORIES_WITH_DATA = [
    "Skincare",
    "Makeup",
    "Haircare & Styling",
    "Bath & Body Care",
    "Fragrance",
]

# Default: category with no data (expect failure with "No trending products")
DEFAULT_EMPTY_CATEGORY = "Eye & Ear Care"


def run_one(category: str, expect_success: bool, poll_timeout: float = 120.0) -> bool:
    """Run e2e-llm-report.py for one category; return True if result matches expect_success."""
    cmd = [
        sys.executable,
        E2E_SCRIPT,
        "--category", category,
        "--poll-timeout", str(int(poll_timeout)),
    ]
    result = subprocess.run(cmd, cwd=repo_root)
    ok = result.returncode == 0
    return ok == expect_success


def main():
    parser = argparse.ArgumentParser(
        description="E2E LLM report test across multiple categories (success) and one empty (expected failure)."
    )
    parser.add_argument(
        "--categories",
        nargs="*",
        default=DEFAULT_CATEGORIES_WITH_DATA,
        help="L2 categories that should have data (expect success)",
    )
    parser.add_argument(
        "--empty-category",
        default=DEFAULT_EMPTY_CATEGORY,
        help="L2 category with no data (expect 'No trending products' failure)",
    )
    parser.add_argument(
        "--skip-empty-test",
        action="store_true",
        help="Do not run the empty-category test",
    )
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=120.0,
    )
    args = parser.parse_args()

    if not os.path.isfile(E2E_SCRIPT):
        print(f"Script not found: {E2E_SCRIPT}", file=sys.stderr)
        sys.exit(2)

    failed = []
    passed = []

    for category in args.categories:
        print(f"\n--- Category: {category} (expect success) ---")
        if run_one(category, expect_success=True, poll_timeout=args.poll_timeout):
            passed.append(category)
        else:
            failed.append((category, "expected success"))

    if not args.skip_empty_test:
        print(f"\n--- Empty category: {args.empty_category} (expect no products) ---")
        if run_one(args.empty_category, expect_success=False, poll_timeout=args.poll_timeout):
            passed.append(f"{args.empty_category} (no data, failed as expected)")
        else:
            failed.append((args.empty_category, "expected failure (no data) but got success"))

    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Passed: {len(passed)}")
    for p in passed:
        print(f"    - {p}")
    if failed:
        print(f"  Failed: {len(failed)}")
        for cat, reason in failed:
            print(f"    - {cat}: {reason}")
        sys.exit(1)
    print("All E2E checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
