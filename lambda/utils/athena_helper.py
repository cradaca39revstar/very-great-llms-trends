"""
Athena Query Helper Module
Wrapper functions for executing Athena queries and parsing results
"""

import os
import time
from typing import List, Dict
import boto3
from botocore.exceptions import ClientError

# AWS Athena client
athena_client = boto3.client('athena', region_name=os.environ.get('AWS_REGION_NAME', 'us-east-1'))
s3_client = boto3.client('s3', region_name=os.environ.get('AWS_REGION_NAME', 'us-east-1'))


def query_athena_top_products(
    l2_category: str,
    workgroup: str,
    database: str,
    limit: int = 5
) -> List[Dict]:
    """
    Query Athena for top trending products by L2 category
    
    Args:
        l2_category: L2 product category (e.g., "Skincare")
        workgroup: Athena workgroup name
        database: Glue database name
        limit: Number of top products (default 5)
        
    Returns:
        List of product dictionaries with all required fields
        
    Raises:
        Exception: If query fails or times out
    """
    print(f"Querying Athena for top {limit} products in '{l2_category}'")
    
    # Build SQL query
    sql_query = build_top_products_query(l2_category, database, limit)
    
    # Execute query
    execution_id = execute_query(sql_query, workgroup)
    
    # Wait for completion
    wait_for_query_completion(execution_id, timeout=30)
    
    # Get and parse results
    results = get_query_results(execution_id)
    
    print(f"Athena query returned {len(results)} products")
    return results


def build_top_products_query(l2_category: str, database: str, limit: int = 5) -> str:
    """
    Build SQL query for top products by L2 category.
    For poc, uses the only (year, month_num) present in the table; later can be
    extended to validate specific date ranges.
    """
    # Escape single quotes in category name
    safe_category = l2_category.replace("'", "''")
    table = f"{database}.curated_beauty_products"
    # Use the only partition(s) that exist in the table (poc: one date; later: validate specific dates)
    query = f"""
    WITH latest_partition AS (
      SELECT DISTINCT year, month_num FROM {table}
    ),
    ranked_products AS (
      SELECT 
        p.product_id,
        p.product_name,
        p.shop_name,
        p.l2_category,
        p.revenue_usd,
        p.mom_growth_pct,
        p.item_sold,
        ROW_NUMBER() OVER (
          PARTITION BY p.l2_category 
          ORDER BY p.revenue_usd DESC, p.mom_growth_pct DESC
        ) as revenue_rank
      FROM {table} p
      INNER JOIN latest_partition lp ON p.year = lp.year AND p.month_num = lp.month_num
      WHERE p.l2_category = '{safe_category}'
        AND p.data_quality_score >= 0.95
    )
    SELECT 
      product_id,
      product_name,
      shop_name,
      l2_category,
      revenue_usd,
      mom_growth_pct,
      item_sold,
      revenue_rank
    FROM ranked_products
    WHERE revenue_rank <= {limit}
    ORDER BY revenue_rank
    """
    return query.strip()


def execute_query(sql: str, workgroup: str) -> str:
    """
    Execute Athena query and return execution ID
    
    Args:
        sql: SQL query string
        workgroup: Athena workgroup name
        
    Returns:
        Query execution ID
        
    Raises:
        ClientError: If query submission fails
    """
    try:
        bucket = os.environ.get("ATHENA_RESULT_BUCKET")
        if not bucket:
            raise Exception("ATHENA_RESULT_BUCKET not set")
        response = athena_client.start_query_execution(
            QueryString=sql,
            WorkGroup=workgroup,
            ResultConfiguration={"OutputLocation": f"s3://{bucket}/"},
        )
        execution_id = response['QueryExecutionId']
        print(f"Athena query started: {execution_id}")
        return execution_id
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        print(f"Athena query submission failed: {error_code} - {error_message}")
        raise Exception(f"Athena query failed: {error_message}")


def wait_for_query_completion(execution_id: str, timeout: int = 30) -> str:
    """
    Poll Athena query until completion or timeout
    
    Args:
        execution_id: Query execution ID
        timeout: Maximum wait time in seconds
        
    Returns:
        Final query state (SUCCEEDED, FAILED, or CANCELLED)
        
    Raises:
        Exception: If query fails or times out
    """
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            raise Exception(f"Athena query timed out after {timeout} seconds")
        
        try:
            response = athena_client.get_query_execution(QueryExecutionId=execution_id)
            state = response['QueryExecution']['Status']['State']
            
            if state == 'SUCCEEDED':
                print(f"Athena query succeeded: {execution_id}")
                return state
            elif state == 'FAILED':
                reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                raise Exception(f"Athena query failed: {reason}")
            elif state == 'CANCELLED':
                raise Exception("Athena query was cancelled")
            else:
                # Still running (QUEUED or RUNNING)
                time.sleep(1)
                
        except ClientError as e:
            error_message = e.response['Error']['Message']
            raise Exception(f"Failed to check query status: {error_message}")


def get_query_results(execution_id: str) -> List[Dict]:
    """
    Get Athena query results and parse into list of dicts
    
    Args:
        execution_id: Query execution ID
        
    Returns:
        List of product dictionaries
        
    Raises:
        Exception: If results retrieval fails
    """
    try:
        response = athena_client.get_query_results(QueryExecutionId=execution_id)
        
        # Extract column names from first row
        result_set = response['ResultSet']
        rows = result_set['Rows']
        
        if len(rows) < 2:  # No data rows (only header)
            return []
        
        # Parse column names
        columns = [col['VarCharValue'] for col in rows[0]['Data']]
        
        # Parse data rows
        products = []
        for row in rows[1:]:  # Skip header row
            values = [col.get('VarCharValue', '') for col in row['Data']]
            product = dict(zip(columns, values))
            
            # Convert numeric fields
            product = convert_numeric_fields(product)
            
            products.append(product)
        
        return products
        
    except ClientError as e:
        error_message = e.response['Error']['Message']
        raise Exception(f"Failed to get query results: {error_message}")


def convert_numeric_fields(product: Dict) -> Dict:
    """
    Convert string values to appropriate numeric types
    
    Args:
        product: Product dict with string values
        
    Returns:
        Product dict with converted numeric fields
    """
    # Fields that should be numeric
    numeric_fields = {
        'product_id': int,
        'revenue_usd': float,
        'mom_growth_pct': float,
        'item_sold': int,
        'revenue_rank': int
    }
    
    for field, field_type in numeric_fields.items():
        if field in product:
            raw = product[field]
            # Treat empty string, None, or whitespace as missing -> use 0
            if raw is None or (isinstance(raw, str) and str(raw).strip() == ''):
                product[field] = 0 if field_type in (int, float) else product[field]
            else:
                try:
                    product[field] = field_type(product[field])
                except (ValueError, TypeError):
                    print(f"Warning: Failed to convert {field} to {field_type.__name__}")
                    product[field] = 0 if field_type in (int, float) else product[field]
    
    return product


def validate_athena_connection(workgroup: str, database: str) -> bool:
    """
    Validate Athena connection and database access
    
    Args:
        workgroup: Athena workgroup name
        database: Database name to check
        
    Returns:
        True if connection is valid, False otherwise
    """
    try:
        # Simple test query
        test_query = f"SELECT 1 FROM {database}.curated_beauty_products LIMIT 1"
        execution_id = execute_query(test_query, workgroup)
        wait_for_query_completion(execution_id, timeout=10)
        print(f"Athena connection validated: workgroup={workgroup}, database={database}")
        return True
    except Exception as e:
        print(f"Athena connection validation failed: {str(e)}")
        return False
