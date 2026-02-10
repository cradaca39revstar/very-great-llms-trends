/**
 * LLM Trending Products API client.
 * Contract: POST body { query }, header Authorization: Bearer <IdToken>.
 * Returns typed success (report, request_id, execution_time_ms, product_count) or error (message, request_id, supported_categories).
 */
import type { TrendQueryResponse, TrendQueryError } from '../types/api';

const API_URL = import.meta.env.VITE_API_URL ?? '';

export async function queryTrendingProducts(
  idToken: string,
  query: string
): Promise<TrendQueryResponse> {
  if (!API_URL) {
    const err: TrendQueryError = {
      error: true,
      message: 'VITE_API_URL is not set. Configure it in .env.local or Amplify environment variables.',
      request_id: 'client-config',
    };
    return err;
  }

  const res = await fetch(API_URL, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${idToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query }),
  });

  const body = await res.json().catch(() => ({}));

  if (!res.ok) {
    const err: TrendQueryError = {
      error: true,
      message: (body as TrendQueryError).message ?? `HTTP ${res.status}`,
      request_id: (body as TrendQueryError).request_id ?? 'unknown',
      supported_categories: (body as TrendQueryError).supported_categories ?? undefined,
    };
    return err;
  }

  if ((body as TrendQueryError).error === true) {
    return body as TrendQueryError;
  }

  return body as TrendQueryResponse;
}
