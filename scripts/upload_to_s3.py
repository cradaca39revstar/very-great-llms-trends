#!/usr/bin/env python3
"""
Upload CSV files to S3 Raw Zone
Beauty Products Data Lake - Data Ingestion Script

Usage:
    python scripts/upload_to_s3.py <file_path>
    python scripts/upload_to_s3.py --date YYYY-MM-DD
    python scripts/upload_to_s3.py --date 2024-04-17 --bucket custom-bucket-name
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Default S3 bucket (can be overridden)
DEFAULT_BUCKET = "very-great-products-raw-us-east-1-poc"
DEFAULT_REGION = "us-east-1"


def parse_date_from_path(file_path: str) -> tuple:
    """Extract year, month, day from file path or filename."""
    path = Path(file_path)
    
    # Try to extract from directory structure: data/raw/YYYY/MM/DD/file.csv
    parts = path.parts
    if 'raw' in parts:
        raw_idx = parts.index('raw')
        if len(parts) > raw_idx + 3:
            try:
                year = int(parts[raw_idx + 1])
                month = int(parts[raw_idx + 2])
                day = int(parts[raw_idx + 3])
                return year, month, day
            except (ValueError, IndexError):
                pass
    
    # Try to extract from filename: beauty-products_YYYYMMDD.csv
    filename = path.stem
    if '_' in filename:
        date_part = filename.split('_')[-1]
        if len(date_part) == 8 and date_part.isdigit():
            year = int(date_part[:4])
            month = int(date_part[4:6])
            day = int(date_part[6:8])
            return year, month, day
    
    # Default to today's date
    today = datetime.now()
    return today.year, today.month, today.day


def upload_file_to_s3(
    file_path: str,
    bucket: str = DEFAULT_BUCKET,
    region: str = DEFAULT_REGION,
    year: int = None,
    month: int = None,
    day: int = None
) -> bool:
    """
    Upload a CSV file to S3 raw zone.
    
    Args:
        file_path: Local path to CSV file
        bucket: S3 bucket name
        region: AWS region
        year: Year for S3 path (auto-detected if None)
        month: Month for S3 path (auto-detected if None)
        day: Day for S3 path (auto-detected if None)
    
    Returns:
        True if successful, False otherwise
    """
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found: {file_path}")
        return False
    
    # Auto-detect date if not provided
    if not all([year, month, day]):
        year, month, day = parse_date_from_path(file_path)
    
    # Construct S3 key
    filename = os.path.basename(file_path)
    s3_key = f"landing/beauty-products/{year}/{month:02d}/{day:02d}/{filename}"
    
    print(f"📤 Uploading: {file_path}")
    print(f"   → s3://{bucket}/{s3_key}")
    
    try:
        s3_client = boto3.client('s3', region_name=region)
        
        # Upload file
        s3_client.upload_file(
            file_path,
            bucket,
            s3_key,
            ExtraArgs={
                'ContentType': 'text/csv',
                'ServerSideEncryption': 'AES256',
                'Metadata': {
                    'uploaded-by': os.getenv('USER', 'unknown'),
                    'upload-date': datetime.now().isoformat(),
                    'source': 'local-upload-script'
                }
            }
        )
        
        print(f"✅ Successfully uploaded to S3")
        print(f"   Full S3 path: s3://{bucket}/{s3_key}")
        return True
        
    except NoCredentialsError:
        print("❌ Error: AWS credentials not found")
        print("   Configure credentials using: aws configure")
        return False
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == 'NoSuchBucket':
            print(f"❌ Error: Bucket '{bucket}' does not exist")
            print(f"   Make sure the bucket exists or deploy infrastructure first")
        elif error_code == 'AccessDenied':
            print(f"❌ Error: Access denied to bucket '{bucket}'")
            print(f"   Check your IAM permissions")
        else:
            print(f"❌ Error uploading file: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def upload_directory_to_s3(
    directory: str,
    bucket: str = DEFAULT_BUCKET,
    region: str = DEFAULT_REGION,
    year: int = None,
    month: int = None,
    day: int = None
) -> int:
    """
    Upload all CSV files from a directory to S3.
    
    Returns:
        Number of files successfully uploaded
    """
    if not os.path.isdir(directory):
        print(f"❌ Error: Directory not found: {directory}")
        return 0
    
    csv_files = list(Path(directory).glob("*.csv"))
    
    if not csv_files:
        print(f"⚠️  No CSV files found in: {directory}")
        return 0
    
    print(f"📁 Found {len(csv_files)} CSV file(s) in directory")
    
    success_count = 0
    for csv_file in csv_files:
        if upload_file_to_s3(str(csv_file), bucket, region, year, month, day):
            success_count += 1
        print()  # Empty line between files
    
    print(f"✅ Uploaded {success_count}/{len(csv_files)} file(s) successfully")
    return success_count


def main():
    parser = argparse.ArgumentParser(
        description="Upload CSV files to S3 Raw Zone for Beauty Products Data Lake",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload a specific file
  python scripts/upload_to_s3.py data/raw/2024/04/17/beauty-products_20240417.csv
  
  # Upload all files for a specific date
  python scripts/upload_to_s3.py --date 2024-04-17
  
  # Upload to a custom bucket
  python scripts/upload_to_s3.py --date 2024-04-17 --bucket my-custom-bucket
        """
    )
    
    parser.add_argument(
        'file_path',
        nargs='?',
        help='Path to CSV file or directory to upload'
    )
    
    parser.add_argument(
        '--date',
        type=str,
        help='Date in YYYY-MM-DD format (for directory uploads)'
    )
    
    parser.add_argument(
        '--bucket',
        type=str,
        default=DEFAULT_BUCKET,
        help=f'S3 bucket name (default: {DEFAULT_BUCKET})'
    )
    
    parser.add_argument(
        '--region',
        type=str,
        default=DEFAULT_REGION,
        help=f'AWS region (default: {DEFAULT_REGION})'
    )
    
    args = parser.parse_args()
    
    # Parse date if provided
    year = month = day = None
    if args.date:
        try:
            date_obj = datetime.strptime(args.date, '%Y-%m-%d')
            year, month, day = date_obj.year, date_obj.month, date_obj.day
        except ValueError:
            print(f"❌ Error: Invalid date format '{args.date}'. Use YYYY-MM-DD")
            sys.exit(1)
    
    # Determine if file or directory
    if not args.file_path:
        if args.date:
            # Upload directory for specific date
            directory = f"data/raw/{year}/{month:02d}/{day:02d}"
            if not os.path.exists(directory):
                print(f"❌ Error: Directory not found: {directory}")
                sys.exit(1)
            upload_directory_to_s3(directory, args.bucket, args.region, year, month, day)
        else:
            parser.print_help()
            sys.exit(1)
    else:
        if os.path.isdir(args.file_path):
            # Upload directory
            upload_directory_to_s3(args.file_path, args.bucket, args.region, year, month, day)
        elif os.path.isfile(args.file_path):
            # Upload single file
            success = upload_file_to_s3(args.file_path, args.bucket, args.region, year, month, day)
            sys.exit(0 if success else 1)
        else:
            print(f"❌ Error: Path not found: {args.file_path}")
            sys.exit(1)


if __name__ == '__main__':
    main()
