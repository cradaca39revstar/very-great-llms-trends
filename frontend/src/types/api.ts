/**
 * API contract types for the LLM Trending Products backend.
 * Matches Lambda response: success (status, request_id, report, ...) and error (error, message, request_id, supported_categories).
 */

export interface ReportProduct {
  rank: number;
  product_id: number | null;
  brand_name: string;
  product_name: string;
  image_url: string;
  brand_url: string;
  description: string;
  revenue_trend: string;
  revenue_scale: string;
  category_rank: string;
  supporting_trends: string[];
}

export interface Report {
  query: string;
  category: string;
  generated_at: string;
  data_period: string;
  products: ReportProduct[];
}

/** Success response from POST /trending-products/query (HTTP 200, status === 'success'). */
export interface TrendQuerySuccess {
  status: 'success';
  request_id: string;
  query: string;
  category: string;
  report: Report;
  pdf_url: string | null;
  execution_time_ms: number;
  product_count: number;
}

/** Error response from API (HTTP 4xx/5xx or body.error === true). */
export interface TrendQueryError {
  error: true;
  message: string;
  request_id: string;
  supported_categories?: string[] | null;
}

export type TrendQueryResponse = TrendQuerySuccess | TrendQueryError;

export function isTrendQueryError(r: TrendQueryResponse): r is TrendQueryError {
  return 'error' in r && r.error === true;
}

export function isTrendQuerySuccess(r: TrendQueryResponse): r is TrendQuerySuccess {
  return 'status' in r && r.status === 'success';
}

/** L2 categories supported by the backend (for selector / validation). */
export const SUPPORTED_L2_CATEGORIES = [
  'Skincare',
  'Haircare & Styling',
  'Makeup',
  'Bath & Body Care',
  'Fragrance',
  'Tools & Accessories',
] as const;
