#!/usr/bin/env python3
"""
Generate sample CSV files for E2E testing: multiple dates (last 30 days), all L2 categories
except one (empty category) to test "no records" message.

Usage:
  python scripts/generate_sample_data_for_categories.py --output-dir data/raw
  python scripts/generate_sample_data_for_categories.py --output-dir data/raw --empty-category "Eye & Ear Care"
  python scripts/generate_sample_data_for_categories.py --output-dir data/raw --dates 2026-01-15 2026-02-01
"""

import argparse
import csv
import os
from datetime import datetime, timedelta
from pathlib import Path

# L2 categories matching the frontend dropdown (one will be left empty)
L2_CATEGORIES = [
    "Bath & Body Care",
    "Eye & Ear Care",
    "Fragrance",
    "Haircare & Styling",
    "Hand, Foot & Nail Care",
    "Makeup",
    "Men's Care",
    "Nasal & Oral Care",
    "Personal Care Appliances",
    "Skincare",
    "Special Personal Care",
]

# Simple L3 per L2 for realistic data
L3_BY_L2 = {
    "Bath & Body Care": "Bathing Accessories",
    "Eye & Ear Care": "Eye Treatments",
    "Fragrance": "Unisex Fragrance",
    "Haircare & Styling": "Hair Brushes & Combs",
    "Hand, Foot & Nail Care": "Nail Treatments",
    "Makeup": "Makeup Base and Primers",
    "Men's Care": "Shaving & Grooming",
    "Nasal & Oral Care": "Teeth Whitening",
    "Personal Care Appliances": "Curlers & Straighteners",
    "Skincare": "Serums & Essences",
    "Special Personal Care": "Personal Care Kits",
}

L1 = "Beauty & Personal Care"
SHOPS = ["BeautyChoiceUSA", "GlamourStore", "NaturalBeauty", "Revolve", "cocomintbeauty"]


def normalize_empty_category(name: str) -> str:
    """Compare category ignoring case/whitespace."""
    return (name or "").strip().lower()


def generate_rows_for_date(
    base_date: datetime,
    categories_to_fill: list[str],
    rows_per_category: int = 8,
    base_id: int = 1729383941730701675,
) -> list[dict]:
    """Generate CSV rows for one date; only for categories in categories_to_fill."""
    month_str = f"{base_date.month}/{base_date.day}/{base_date.year}"
    rows = []
    product_id = base_id
    for l2 in categories_to_fill:
        l3 = L3_BY_L2.get(l2, "Other")
        for i in range(rows_per_category):
            revenue = 50000 + (i * 15000) + (hash(l2) % 20000)
            item_sold = 1000 + (i * 500) + (hash(l2) % 500)
            price = round(revenue / item_sold, 2)
            mom = [-42, 10, 23, -12, 67, 8, -24, 39][i % 8]
            rows.append({
                "Month": month_str,
                "Product Id": product_id,
                "Product Name": f"Sample Product {l2[:20]} #{i+1}",
                "Shop Name": SHOPS[i % len(SHOPS)],
                "L1 category": L1,
                "L2 category": l2,
                "L3 category": l3,
                "Item Sold": f"{item_sold:,}",  # CSV writer will quote (comma inside)
                "Revenue": f"${revenue:,}.00 ",
                "Avg. Unit Price": f"${price} ",
                "MoM Growth %": f"{mom}%",
            })
            product_id += 1
    return rows


def write_csv(file_path: Path, rows: list[dict]) -> None:
    """Write CSV with header; numeric-like fields written as in sample (with quotes where needed)."""
    fieldnames = [
        "Month", "Product Id", "Product Name", "Shop Name",
        "L1 category", "L2 category", "L3 category",
        "Item Sold", "Revenue", "Avg. Unit Price", "MoM Growth %",
    ]
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    parser = argparse.ArgumentParser(
        description="Generate sample CSVs for E2E: multiple dates, all L2 categories except one (empty)."
    )
    parser.add_argument(
        "--output-dir",
        default="data/raw",
        help="Base directory for output (e.g. data/raw); files go under YYYY/MM/DD/",
    )
    parser.add_argument(
        "--empty-category",
        default="Eye & Ear Care",
        help="L2 category to leave with NO data (for 'no records' test)",
    )
    parser.add_argument(
        "--dates",
        nargs="*",
        help="Dates YYYY-MM-DD; default: last 30 days (2 dates: today and 15 days ago)",
    )
    parser.add_argument(
        "--rows-per-category",
        type=int,
        default=8,
        help="Rows to generate per category per date",
    )
    args = parser.parse_args()

    empty_norm = normalize_empty_category(args.empty_category)
    categories_to_fill = [
        c for c in L2_CATEGORIES
        if normalize_empty_category(c) != empty_norm
    ]
    if len(categories_to_fill) == len(L2_CATEGORIES):
        print(f"Warning: '{args.empty_category}' did not match any L2 category; all categories will have data.")
        categories_to_fill = L2_CATEGORIES[:-1]  # drop last so one is empty
    else:
        print(f"Empty category (no data): {args.empty_category}")
    print(f"Categories with data ({len(categories_to_fill)}): {', '.join(categories_to_fill)}")

    if args.dates:
        dates = []
        for d in args.dates:
            try:
                dates.append(datetime.strptime(d, "%Y-%m-%d"))
            except ValueError:
                print(f"Invalid date '{d}', use YYYY-MM-DD")
                return 1
    else:
        # Last 30 days: 4 dates so we span 2 months (e.g. year=2026, month_num=1 and 2)
        today = datetime.now()
        dates = [
            today - timedelta(days=30),
            today - timedelta(days=20),
            today - timedelta(days=10),
            today,
        ]

    output_dir = Path(args.output_dir)
    for base_date in dates:
        y, m, d = base_date.year, base_date.month, base_date.day
        dir_path = output_dir / str(y) / f"{m:02d}" / f"{d:02d}"
        dir_path.mkdir(parents=True, exist_ok=True)
        filename = f"beauty-products_{y}{m:02d}{d:02d}.csv"
        file_path = dir_path / filename
        rows = generate_rows_for_date(
            base_date,
            categories_to_fill,
            rows_per_category=args.rows_per_category,
        )
        write_csv(file_path, rows)
        print(f"Wrote {len(rows)} rows -> {file_path}")

    print("Done. Next: upload to S3 (e.g. python scripts/upload_to_s3.py --date YYYY-MM-DD), then run ETL.")
    return 0


if __name__ == "__main__":
    exit(main())
