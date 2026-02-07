/**
 * LLM Trending Products API client (async flow).
 * POST returns 202 with request_id; poll GET /report/{request_id} for status and result.
 */
import type { TrendQueryResponse, TrendQueryError } from '../types/api';

const API_URL = import.meta.env.VITE_API_URL ?? '';

/** Base URL for the API (without /trending-products/query) for GET /report/{request_id}. */
function getReportStatusBaseUrl(): string {
  if (!API_URL) return '';
  return API_URL.replace(/\/trending-products\/query\/?$/, '');
}

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
    const err: TrendQueryError = {
      error: true,
      message: msg,
      request_id: 'client-error',
    };
    return err;
  }

  const body = await res.json().catch(() => ({}));

  if (res.status === 202) {
    return body as TrendQueryResponse;
  }

  if (!res.ok) {
    const status = res.status;
    let message = (body as TrendQueryError).message ?? `HTTP ${status}`;
    if (status === 504) {
      message =
        'The report took longer than 29 seconds (gateway timeout). Try again; the report is now generated asynchronously.';
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

/** Poll report status. Returns success, error, or processing. */
export async function getReportStatus(
  idToken: string,
  requestId: string
): Promise<TrendQueryResponse> {
  const base = getReportStatusBaseUrl();
  if (!base) {
    return {
      error: true,
      message: 'VITE_API_URL is not set.',
      request_id: requestId,
    } as TrendQueryError;
  }
  const url = `${base}/report/${requestId}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${idToken}`,
      },
    });
  } catch (fetchErr) {
    const msg = fetchErr instanceof Error ? fetchErr.message : String(fetchErr);
    return {
      error: true,
      message: msg,
      request_id: requestId,
    } as TrendQueryError;
  }
  const body = await res.json().catch(() => ({}));
  if (res.status === 404) {
    return {
      error: true,
      message: (body as { message?: string }).message ?? 'Report not found',
      request_id: requestId,
    } as TrendQueryError;
  }
  if (!res.ok) {
    return {
      error: true,
      message: (body as TrendQueryError).message ?? `HTTP ${res.status}`,
      request_id: requestId,
    } as TrendQueryError;
  }
  return body as TrendQueryResponse;
}
