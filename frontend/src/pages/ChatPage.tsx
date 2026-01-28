import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { signOut } from 'aws-amplify/auth';
import { fetchAuthSession } from 'aws-amplify/auth';
import { queryTrendingProducts } from '../services/api';
import {
  isTrendQueryError,
  isTrendQuerySuccess,
  SUPPORTED_L2_CATEGORIES,
  type TrendQueryResponse,
  type TrendQuerySuccess,
  type TrendQueryError,
} from '../types/api';

export function ChatPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TrendQueryResponse | null>(null);

  const handleConsult = async () => {
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setResult(null);
    try {
      const session = await fetchAuthSession();
      const token = session.tokens?.idToken?.toString();
      if (!token) {
        setResult({
          error: true,
          message: 'Not authenticated. Sign in again.',
          request_id: 'client-auth',
        });
        setLoading(false);
        return;
      }
      const res = await queryTrendingProducts(token, q);
      setResult(res);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setResult({
        error: true,
        message: msg,
        request_id: 'client-error',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    await signOut();
    navigate('/login', { replace: true });
  };

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '1rem' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1>LLM Trending Products</h1>
        <button type="button" onClick={handleLogout}>Sign out</button>
      </header>

      <section style={{ marginBottom: '1.5rem' }}>
        <label htmlFor="query">Query (e.g. &quot;What are the top trending products in Skincare?&quot;)</label>
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
          <input
            id="query"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="What are the top trending products in Skincare?"
            style={{ flex: 1, padding: '0.5rem' }}
          />
          <button type="button" onClick={handleConsult} disabled={loading}>
            {loading ? 'Loading…' : 'Get report'}
          </button>
        </div>
        <div style={{ marginTop: '0.5rem' }}>
          <span style={{ marginRight: '0.5rem' }}>Or pick L2 category:</span>
          <select
            value={query}
            onChange={(e) => setQuery(e.target.value || '')}
            style={{ padding: '0.25rem' }}
          >
            <option value="">--</option>
            {SUPPORTED_L2_CATEGORIES.map((c) => (
              <option key={c} value={`What are the top trending products in ${c}?`}>{c}</option>
            ))}
          </select>
        </div>
      </section>

      {result && (
        <section>
          {isTrendQueryError(result) && <ErrorView data={result} />}
          {isTrendQuerySuccess(result) && <SuccessView data={result} />}
        </section>
      )}
    </div>
  );
}

function ErrorView({ data }: { data: TrendQueryError }) {
  return (
    <div className="error" style={{ padding: '1rem', border: '1px solid #f66', borderRadius: 4 }}>
      <p><strong>Error:</strong> {data.message}</p>
      <p className="meta">Request ID: {data.request_id}</p>
      {data.supported_categories && data.supported_categories.length > 0 && (
        <p className="meta">Supported categories: {data.supported_categories.join(', ')}</p>
      )}
    </div>
  );
}

function SuccessView({ data }: { data: TrendQuerySuccess }) {
  const { report, pdf_url, request_id, execution_time_ms, product_count } = data;
  return (
    <div style={{ padding: '1rem', border: '1px solid #333', borderRadius: 4 }}>
      <div className="meta" style={{ marginBottom: '1rem' }}>
        <span>Request ID: {request_id}</span>
        <span style={{ marginLeft: '1rem' }}>Execution: {execution_time_ms} ms</span>
        <span style={{ marginLeft: '1rem' }}>Products: {product_count}</span>
      </div>
      {pdf_url && (
        <p style={{ marginBottom: '1rem' }}>
          <a href={pdf_url} target="_blank" rel="noreferrer">Download PDF</a>
        </p>
      )}
      <h3>{report.category} – {report.data_period}</h3>
      <p className="meta">Generated at {report.generated_at}</p>
      <ul style={{ listStyle: 'none', padding: 0 }}>
        {report.products.map((p) => (
          <li key={p.rank} style={{ marginBottom: '1rem', padding: '0.75rem', background: '#1a1a1a', borderRadius: 4 }}>
            <strong>#{p.rank}</strong> {p.product_name} – {p.brand_name}
            <br />
            <span className="meta">{p.revenue_trend} · {p.revenue_scale} · Rank {p.category_rank}</span>
            {p.description && <p style={{ margin: '0.5rem 0 0', fontSize: '0.9rem' }}>{p.description}</p>}
            {p.brand_url && <a href={p.brand_url} target="_blank" rel="noreferrer">Brand</a>}
          </li>
        ))}
      </ul>
    </div>
  );
}
