#!/usr/bin/env python3
"""
End-to-end test for the LLM Trending Products report flow.

Flow: Cognito auth -> POST /trending-products/query -> poll GET /report/{request_id}
      until completed/failed -> assert response structure and content.

Usage:
  From project root (with Terraform applied and Lambda deployed):
    python scripts/e2e-llm-report.py
    python scripts/e2e-llm-report.py --category "Haircare & Styling"
    python scripts/e2e-llm-report.py --poll-timeout 120

Environment (optional override):
  COGNITO_USERNAME, COGNITO_PASSWORD  Defaults: verygreat@test.com / VeryGreat123!
  AWS_REGION                           Default: us-east-1
"""

import argparse
import json
import os
import subprocess
import sys
import time

try:
    import requests
except ImportError:
    print("Install requests: pip install requests", file=sys.stderr)
    sys.exit(1)

try:
    import boto3
except ImportError:
    print("Install boto3: pip install boto3", file=sys.stderr)
    sys.exit(1)


def get_terraform_output(name: str, terraform_dir: str) -> str:
    out = subprocess.run(
        ["terraform", "output", "-raw", name],
        cwd=terraform_dir,
        capture_output=True,
        text=True,
    )
    if out.returncode != 0:
        raise RuntimeError(f"terraform output -raw {name} failed: {out.stderr}")
    return out.stdout.strip()


def get_id_token(cognito_client_id: str, username: str, password: str, region: str) -> str:
    client = boto3.client("cognito-idp", region_name=region)
    resp = client.initiate_auth(
        AuthFlow="USER_PASSWORD_AUTH",
        ClientId=cognito_client_id,
        AuthParameters={"USERNAME": username, "PASSWORD": password},
    )
    token = resp.get("AuthenticationResult", {}).get("IdToken")
    if not token:
        raise RuntimeError("No IdToken in Cognito response")
    return token


def post_query(api_url: str, token: str, query: str) -> dict:
    r = requests.post(
        api_url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"query": query},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def get_report_status(base_url: str, token: str, request_id: str) -> dict:
    url = f"{base_url}/report/{request_id}"
    r = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def run_e2e(
    terraform_dir: str,
    category: str,
    poll_interval: float,
    poll_timeout: float,
    username: str,
    password: str,
    region: str,
) -> bool:
    query = f"What are the top trending products in {category}?"
    print(f"E2E: category={category!r} query={query[:60]}...")
    print("Getting Terraform outputs...")
    api_url = get_terraform_output("api_gateway_url", terraform_dir)
    report_base = get_terraform_output("api_gateway_report_status_base", terraform_dir)
    cognito_client_id = get_terraform_output("cognito_client_id", terraform_dir)
    print("Getting IdToken...")
    token = get_id_token(cognito_client_id, username, password, region)
    print("POST /trending-products/query...")
    body = post_query(api_url, token, query)

    if body.get("error"):
        print(f"API error: {body.get('message', body)}")
        return False

    if body.get("status") == "processing":
        request_id = body["request_id"]
        print(f"Request ID: {request_id}, polling every {poll_interval}s (timeout {poll_timeout}s)...")
        start = time.monotonic()
        while (time.monotonic() - start) < poll_timeout:
            time.sleep(poll_interval)
            status_resp = get_report_status(report_base, token, request_id)
            if status_resp.get("error"):
                print(f"Report failed: {status_resp.get('message', status_resp)}")
                return False
            if status_resp.get("status") == "success":
                body = status_resp
                break
            if status_resp.get("status") == "failed":
                print(f"Report status failed: {status_resp.get('error', status_resp)}")
                return False
        else:
            print("Poll timeout")
            return False
    elif body.get("status") != "success":
        print(f"Unexpected response: {body}")
        return False

    # Assertions
    report = body.get("report") or {}
    errors = []

    if body.get("status") != "success":
        errors.append("status != success")
    if not report.get("category"):
        errors.append("report.category missing")
    mc = report.get("market_context") or []
    if len(mc) < 1 or len(mc) > 5:
        errors.append(f"report.market_context length must be 1-5, got {len(mc)}")
    brand = report.get("brand_proposal") or {}
    if not brand.get("brand_name"):
        errors.append("report.brand_proposal.brand_name missing")
    if not brand.get("inspired_by_product"):
        errors.append("report.brand_proposal.inspired_by_product missing (backend-injected)")
    ideas = report.get("product_ideas") or []
    if len(ideas) != 1:
        errors.append(f"report.product_ideas length must be 1, got {len(ideas)}")
    if not body.get("pdf_url"):
        errors.append("pdf_url missing")

    if errors:
        print("Assertions failed:")
        for e in errors:
            print(f"  - {e}")
        return False

    print("OK: status=success, category=%s, market_context=%d, brand=%s, product_ideas=1, pdf_url present"
          % (report.get("category"), len(mc), brand.get("brand_name")))
    if body.get("execution_time_ms"):
        print("  execution_time_ms: %s" % body["execution_time_ms"])
    return True


def main():
    parser = argparse.ArgumentParser(description="E2E test for LLM report flow")
    parser.add_argument("--terraform-dir", default=None, help="Path to terraform dir (default: repo root/terraform)")
    parser.add_argument("--category", default="Skincare", help="L2 category to query")
    parser.add_argument("--poll-interval", type=float, default=3.0, help="Seconds between poll")
    parser.add_argument("--poll-timeout", type=float, default=90.0, help="Max seconds to wait for report")
    parser.add_argument("--username", default=os.environ.get("COGNITO_USERNAME", "verygreat@test.com"))
    parser.add_argument("--password", default=os.environ.get("COGNITO_PASSWORD", "VeryGreat123!"))
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    terraform_dir = args.terraform_dir or os.path.join(repo_root, "terraform")
    if not os.path.isdir(terraform_dir):
        print(f"Terraform dir not found: {terraform_dir}", file=sys.stderr)
        sys.exit(2)

    ok = run_e2e(
        terraform_dir=terraform_dir,
        category=args.category,
        poll_interval=args.poll_interval,
        poll_timeout=args.poll_timeout,
        username=args.username,
        password=args.password,
        region=args.region,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
