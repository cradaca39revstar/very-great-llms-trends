# Raw Data Files

This directory contains the original CSV files that will be uploaded to S3 for processing.

## Directory Structure

```
data/raw/
├── YYYY/           # Year (e.g., 2024)
│   └── MM/         # Month (e.g., 04)
│       └── DD/      # Day (e.g., 17)
│           └── beauty-products_YYYYMMDD.csv
```

## Usage

### Upload a single file to S3

```bash
# From project root
aws s3 cp data/raw/2024/04/17/beauty-products_20240417.csv \
  s3://very-great-products-raw-us-east-1-poc/landing/beauty-products/2024/04/17/
```

### Upload all files for a specific date

```bash
# Upload all files for April 17, 2024
aws s3 sync data/raw/2024/04/17/ \
  s3://very-great-products-raw-us-east-1-poc/landing/beauty-products/2024/04/17/
```

### Use the upload script

```bash
# Upload a specific file
python scripts/upload_to_s3.py data/raw/2024/04/17/beauty-products_20240417.csv

# Upload all files for a date
python scripts/upload_to_s3.py --date 2024-04-17
```

## File Naming Convention

- Format: `beauty-products_YYYYMMDD.csv`
- Example: `beauty-products_20240417.csv`
- Use lowercase with hyphens
- Include date in filename for traceability

## CSV Format Requirements

The CSV files must have the following columns (in order):

1. Month
2. Product Id
3. Product Name
4. Shop Name
5. L1 category
6. L2 category
7. L3 category
8. Item Sold
9. Revenue
10. Avg. Unit Price
11. MoM Growth %

See `tests/sample-data/valid_input.csv` for an example format.

## Notes

- Files in this directory are **not** automatically processed
- Files must be manually uploaded to S3 using AWS CLI or the upload script
- After upload, the Glue job will process them automatically (if scheduled) or manually triggered
- Keep original files here for backup and reprocessing if needed
