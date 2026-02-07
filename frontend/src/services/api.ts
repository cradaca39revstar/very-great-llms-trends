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

  let res: Response;
  try {
    res = await fetch(API_URL, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${idToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query }),
    });
  } catch (fetchErr) {
    const msg = fetchErr instanceof Error ? fetchErr.message : String(fetchErr);
    const hint =
      msg === 'Failed to fetch' || msg.includes('NetworkError')
        ? ' Often: (1) API took >29s and gateway timed out, (2) wrong VITE_API_URL in .env.local — run "terraform output -raw api_gateway_url" and restart "npm run dev", or (3) CORS.'
        : '';
    const err: TrendQueryError = {
      error: true,
      message: msg + hint,
      request_id: 'client-error',
    };
    return err;
  }

  const body = await res.json().catch(() => ({}));

  if (!res.ok) {
    const status = res.status;
    let message = (body as TrendQueryError).message ?? `HTTP ${status}`;
    if (status === 504) {
      message =
        'The report took longer than 29 seconds (gateway timeout). The PDF may still have been generated. Run .\\scripts\\call-api-llm.ps1 to get the PDF link, or try again.';
    }
    const err: TrendQueryError = {
      error: true,
      message,
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
