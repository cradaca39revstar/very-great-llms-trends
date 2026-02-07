/**
 * API contract types for the LLM Trending Products backend (V2).
 * Success: status, request_id, brand_name, report (market_context, brand_proposal, product_ideas), pdf_url, ...
 * Error: status_code, msg_code, request_id, message, supported_categories.
 */

export interface MarketProduct {
  product_name: string;
  shop_name: string;
  revenue_usd: number;
  mom_growth_pct: number;
  item_sold: number;
  revenue_rank: number;
}

export interface BrandProposal {
  brand_name: string;
  brand_tagline: string;
  brand_story: string;
  brand_values: string[];
  target_demographic: string;
  price_positioning: string;
  distribution_strategy: string;
  brand_personality: string;
  /** Base64 thumbnail (JPEG or PNG). Use as data URL for <img>. */
  logo_image_base64?: string | null;
  logo_image_base64_format?: 'jpeg' | 'png' | null;
}

/** One macro trend: title + paragraph description. */
export interface SupportingTrend {
  title: string;
  description: string;
}

export interface ProductIdea {
  rank: number;
  product_name: string;
  description: string;
  estimated_price_usd: number;
  why_it_would_sell: string;
  key_ingredients: string[];
  /** Intro paragraph before the 5 macro trends (e.g. "Here are 5 macro trends that are driving..."). */
  supporting_trends_intro?: string | null;
  /** 5 macro trends with title and description. Legacy: string[] is still supported in UI. */
  supporting_trends: SupportingTrend[] | string[];
  competitive_advantage: string;
  has_image: boolean;
  image_url?: string;
  /** Base64 thumbnail (JPEG or PNG). Use as data URL for <img>. */
  image_base64?: string | null;
  image_base64_format?: 'jpeg' | 'png' | null;
}

export interface Report {
  query: string;
  category: string;
  generated_at: string;
  data_period: string;
  market_context?: MarketProduct[];
  brand_proposal: BrandProposal;
  product_ideas: ProductIdea[];
}

/** Success response from POST /trending-products/query (HTTP 200, status === 'success'). */
export interface TrendQuerySuccess {
  status: 'success';
  request_id: string;
  query: string;
  category: string;
  brand_name: string;
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
  status_code?: number;
  msg_code?: Array<{ code: string; description: string }>;
}

/** Async flow: POST returns 202 with this; frontend polls GET /report/{request_id} until completed/failed. */
export interface TrendQueryProcessing {
  status: 'processing';
  request_id: string;
  message?: string;
}

export type TrendQueryResponse = TrendQuerySuccess | TrendQueryError | TrendQueryProcessing;

export function isTrendQueryError(r: TrendQueryResponse): r is TrendQueryError {
  return 'error' in r && r.error === true;
}

export function isTrendQuerySuccess(r: TrendQueryResponse): r is TrendQuerySuccess {
  return 'status' in r && r.status === 'success';
}

export function isTrendQueryProcessing(r: TrendQueryResponse): r is TrendQueryProcessing {
  return 'status' in r && r.status === 'processing';
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
