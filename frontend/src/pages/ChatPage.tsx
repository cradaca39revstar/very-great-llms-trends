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
  type ReportProduct,
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
    <div style={{ maxWidth: 820, margin: '0 auto', padding: '1.25rem 1rem' }}>
      <header className="chat-header">
        <div className="chat-header__brand">
          <img
            src="/VG_Logo_White.webp"
            alt="Logo"
            className="chat-header__logo"
          />
          <h1 className="chat-header__title">Trending Products</h1>
        </div>
        <button type="button" className="chat-header__signout" onClick={handleLogout}>
          Sign out
        </button>
      </header>

      <section className="chat-query">
        <label htmlFor="query" className="chat-query__label">
          L2 category request
        </label>
        <div className="chat-query__row">
          <input
            id="query"
            type="text"
            className="chat-query__input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="What are the top trending products in Skincare?"
          />
          <button
            type="button"
            className="chat-query__btn"
            onClick={handleConsult}
            disabled={loading}
          >
            {loading ? 'Loading…' : 'Get report'}
          </button>
        </div>
        <div className="chat-query__select-wrap">
          <span>Or pick L2 category:</span>
          <select
            className="chat-query__select"
            value={query}
            onChange={(e) => setQuery(e.target.value || '')}
          >
            <option value="">--</option>
            {SUPPORTED_L2_CATEGORIES.map((c) => (
              <option key={c} value={`What are the top trending products in ${c}?`}>
                {c}
              </option>
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
    <div className="error-block">
      <p><strong>Error:</strong> {data.message}</p>
      <p className="error-block__meta">Request ID: {data.request_id}</p>
      {data.supported_categories && data.supported_categories.length > 0 && (
        <p className="error-block__meta">
          Supported categories: {data.supported_categories.join(', ')}
        </p>
      )}
    </div>
  );
}

function SuccessView({ data }: { data: TrendQuerySuccess }) {
  const { report, pdf_url, request_id, execution_time_ms, product_count } = data;
  return (
    <div>
      <p className="results-intro">Here&apos;s the answer</p>
      <div className="results-meta">
        <span>Request ID: {request_id}</span>
        <span>Execution: {execution_time_ms} ms</span>
        <span>Products: {product_count}</span>
      </div>
      {pdf_url && (
        <div className="results-pdf">
          <a href={pdf_url} target="_blank" rel="noreferrer" className="results-pdf__btn">
            Download PDF
          </a>
        </div>
      )}
      <h2 className="results-report-title">
        {report.category} – {report.data_period}
      </h2>
      <p className="results-report-date">Generated at {report.generated_at}</p>
      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {report.products.map((p) => (
          <li key={p.rank}>
            <ProductCard product={p} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function ProductCard({ product: p }: { product: ReportProduct }) {
  return (
    <article className="product-card">
      <div className="product-card__rank">#{p.rank} Trending Product</div>

      <div className="product-card__image-wrap">
        {p.image_url ? (
          <img
            src={p.image_url}
            alt={p.product_name}
            className="product-card__image"
          />
        ) : (
          <span className="product-card__image-placeholder">No image</span>
        )}
      </div>

      <div className="product-card__label">Brand Name</div>
      <div className="product-card__value">{p.brand_name}</div>

      <div className="product-card__label">Product</div>
      <div className="product-card__value">{p.product_name}</div>

      {p.brand_url && (
        <>
          <div className="product-card__label">URL to brand website</div>
          <div className="product-card__value">
            <a href={p.brand_url} target="_blank" rel="noreferrer" className="product-card__link">
              {p.brand_url}
            </a>
          </div>
        </>
      )}

      {p.description && (
        <>
          <div className="product-card__label">Description</div>
          <p className="product-card__description">{p.description}</p>
        </>
      )}

      <div className="product-card__metrics">
        <span className="product-card__metric">
          <span className="product-card__metric-label">Revenue Trend:</span>
          {p.revenue_trend}
        </span>
        <span className="product-card__metric">
          <span className="product-card__metric-label">Revenue Scale:</span>
          {p.revenue_scale}
        </span>
        <span className="product-card__metric">
          <span className="product-card__metric-label">Product Rank in Category:</span>
          {p.category_rank}
        </span>
      </div>

      {p.supporting_trends && p.supporting_trends.length > 0 && (
        <>
          <div className="product-card__trends-title">Supporting Trends</div>
          <ul className="product-card__trends-list">
            {p.supporting_trends.map((trend, i) => (
              <li key={i}>{trend}</li>
            ))}
          </ul>
        </>
      )}
    </article>
  );
}
