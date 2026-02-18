/**
 * LLM Trending Products API client (async flow).
 * POST returns 202 with request_id; poll GET /report/{request_id} for status and result.
 */
import type { TrendQueryResponse, TrendQueryError } from '../types/api';

const API_URL = import.meta.env.VITE_API_URL ?? '';

/** Base URL for the API (without /trending-products/query) for GET /report/{request_id} and GET /categories. */
function getApiBaseUrl(): string {
  if (!API_URL) return '';
  return API_URL.replace(/\/trending-products\/query\/?$/, '');
}

export type GetCategoriesResult = { categories: string[]; error?: string };

/** Fetch distinct L2 categories from the backend. On failure returns { categories: [], error: message }. */
export async function getCategories(idToken: string): Promise<GetCategoriesResult> {
  const base = getApiBaseUrl();
  if (!base) return { categories: [], error: 'VITE_API_URL not set or missing base path' };
  const url = `${base}/trending-products/categories`;
  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: { Authorization: `Bearer ${idToken}` },
    });
    const body = await res.json().catch(() => ({}));
    const b = body as { error?: boolean; message?: string; categories?: string[] };
    if (b.error && b.message) return { categories: [], error: b.message };
    if (!res.ok) {
      const msg = b.message || `HTTP ${res.status}`;
      if (res.status === 401) return { categories: [], error: '401 Unauthorized — sign in again' };
      if (res.status === 404) return { categories: [], error: '404 Not Found — deploy API Gateway with GET /trending-products/categories' };
      if (res.status >= 500 && (!msg || /internal server error/i.test(msg)))
        return { categories: [], error: 'Backend 500: redeploy Lambda (deploy-lambda-llm.ps1), set ATHENA_WORKGROUP and ATHENA_DATABASE, and check CloudWatch logs for the real error.' };
      return { categories: [], error: msg };
    }
    const list = b.categories;
    if (!Array.isArray(list)) return { categories: [], error: b.message || 'API did not return a categories list' };
    const categories = list.filter((c): c is string => typeof c === 'string' && c.trim() !== '');
    return { categories };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return { categories: [], error: msg || 'Network error' };
  }
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
  const base = getApiBaseUrl();
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
