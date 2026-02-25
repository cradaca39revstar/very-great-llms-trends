import { useState, useRef, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { signOut } from 'aws-amplify/auth';
import { fetchAuthSession } from 'aws-amplify/auth';
import { queryTrendingProducts, getReportStatus, getCategories } from '../services/api';
import {
  isTrendQueryError,
  isTrendQuerySuccess,
  isTrendQueryProcessing,
  type TrendQueryResponse,
  type TrendQuerySuccess,
  type TrendQueryError,
  type BrandProposal,
  type ProductIdea,
  type SupportingTrend,
} from '../types/api';

const POLL_INTERVAL_MS = 2500;
const POLL_TIMEOUT_MS = 90000;

export function ChatPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TrendQueryResponse | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);
  const [categoriesLoading, setCategoriesLoading] = useState(true);
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollStartRef = useRef<number>(0);

  const stopPolling = useCallback(() => {
    if (pollTimeoutRef.current !== null) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
  }, []);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const loadCategories = useCallback(async () => {
    setCategoriesError(null);
    setCategoriesLoading(true);
    try {
      const session = await fetchAuthSession();
      const token = session.tokens?.idToken?.toString();
      if (!token) {
        setCategoriesError('Not signed in');
        setCategories([]);
        return;
      }
      const { categories: list, error } = await getCategories(token);
      setCategories(list);
      setCategoriesError(error ?? null);
    } catch (e) {
      setCategories([]);
      setCategoriesError(e instanceof Error ? e.message : 'Failed to load categories');
    } finally {
      setCategoriesLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  const handleConsult = async () => {
    const q = query.trim();
    if (!q) return;
    stopPolling();
    setLoading(true);
    setResult(null);
    let res: TrendQueryResponse | undefined;
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
      res = await queryTrendingProducts(token, q);
      if (isTrendQueryProcessing(res)) {
        const requestId = res.request_id;
        setResult(res);
        pollStartRef.current = Date.now();
        const poll = async () => {
          if (Date.now() - pollStartRef.current > POLL_TIMEOUT_MS) {
            stopPolling();
            setResult({
              error: true,
              message:
                'Report is taking longer than expected. You can try again or check back later.',
              request_id: requestId,
            });
            setLoading(false);
            return;
          }
          const statusRes = await getReportStatus(token, requestId);
          if (isTrendQuerySuccess(statusRes)) {
            stopPolling();
            setResult(statusRes);
            setLoading(false);
            return;
          }
          if (isTrendQueryError(statusRes)) {
            stopPolling();
            setResult(statusRes);
            setLoading(false);
            return;
          }
          pollTimeoutRef.current = setTimeout(poll, POLL_INTERVAL_MS);
        };
        pollTimeoutRef.current = setTimeout(poll, POLL_INTERVAL_MS);
        return;
      }
      setResult(res);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setResult({
        error: true,
        message: msg,
        request_id: 'client-error',
      });
    } finally {
      if (res !== undefined && isTrendQueryProcessing(res)) return;
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    await signOut();
    navigate('/login', { replace: true });
  };

  return (
    <div className="chat-layout">
      <header className="chat-header">
        <div className="chat-header__brand">
          <h1 className="chat-header__title-main">Very Great</h1>
          <p className="chat-header__title-sub">Trending Products</p>
        </div>
        <button type="button" className="chat-header__signout" onClick={handleLogout}>
          Sign out
        </button>
      </header>

      <section className="chat-query">
        <h1 className="chat-query__heading">Report Request</h1>
        <p className="chat-query__subtitle">Enter the L2 category request</p>
        <div className="chat-query__row">
          <input
            id="query"
            aria-label="L2 category request"
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
          <h2 className="chat-query__heading chat-query__heading--sub">Or pick L2 category:</h2>
          <select
            className="chat-query__select"
            aria-label="Or pick L2 category"
            value={query}
            onChange={(e) => setQuery(e.target.value || '')}
          >
            <option value="">--</option>
            {categories.map((c) => (
              <option key={c} value={`What are the top trending products in ${c}?`}>
                {c}
              </option>
            ))}
          </select>
          {categoriesLoading && categories.length === 0 && (
            <p className="chat-query__hint" role="status">Loading categories…</p>
          )}
          {!categoriesLoading && categories.length === 0 && (
            <div className="chat-query__hint" role="status">
              <p>
                {categoriesError
                  ? `Could not load categories: ${categoriesError}`
                  : 'No categories in data. Run ETL and, if needed, MSCK REPAIR TABLE in Athena.'}
              </p>
              <button type="button" className="chat-query__retry" onClick={loadCategories}>
                Retry
              </button>
            </div>
          )}
        </div>
      </section>

      {result && (
        <section className="chat-results">
          {isTrendQueryProcessing(result) && (
            <div className="results-intro" aria-live="polite">
              <p>Generating report…</p>
              <p className="results-meta">Request ID: {result.request_id}. Polling every 2–3s (max 90s).</p>
            </div>
          )}
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
  const { report, pdf_url, request_id, execution_time_ms, product_count, brand_name } = data;
  const brand = report.brand_proposal;
  const productIdeas = report.product_ideas ?? [];

  return (
    <div>
      <div className="results-title-block">
        <h2 className="results-report-title results-report-title--top">
          {report.category} – {report.data_period}
        </h2>
        <p className="results-intro">Product Innovation Report</p>
      </div>
      {pdf_url ? (
        <div className="results-pdf results-pdf--top">
          <a href={pdf_url} target="_blank" rel="noreferrer" className="results-pdf__btn">
            Download PDF Report
          </a>
        </div>
      ) : null}
      <div className="results-meta">
        <span>Request ID: {request_id}</span>
        <span>Execution: {execution_time_ms} ms</span>
        <span>Product concepts: {product_count}</span>
      </div>
      <p className="results-report-date">Generated at {report.generated_at}</p>

      {report.market_context && report.market_context.length > 0 && (
        <section className="market-research">
          <h2 className="market-research__title">
            Top {report.market_context.length} Market Trend{report.market_context.length !== 1 ? 's' : ''}
          </h2>
          <p className="market-research__intro">
            Top performing products by revenue, growth, and monthly momentum.
          </p>
          {report.market_context.length < 5 && (
            <p className="market-research__notice">
              Only {report.market_context.length} product{report.market_context.length !== 1 ? 's were' : ' was'} found in the last 30 days for this category.
            </p>
          )}
          <h3 className="market-research__subtitle">Product Highlights</h3>
          <ol className="market-research__list">
            {report.market_context.map((p, i) => (
              <li key={i} className="market-research__item">
                <strong className="market-research__name">{p.product_name}</strong>
                {p.short_description && (
                  <p className="market-research__desc">{p.short_description}</p>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}

      {brand && (
        <BrandProposalCard brand={brand} brandName={brand_name || brand.brand_name} />
      )}

      <ul className="product-idea-list" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {productIdeas.map((p) => (
          <li key={p.rank}>
            <ProductIdeaCard product={p} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function BrandProposalCard({ brand, brandName }: { brand: BrandProposal; brandName: string }) {
  const logoFormat = brand.logo_image_base64_format || 'png';
  const logoDataUrl = brand.logo_image_base64
    ? `data:image/${logoFormat};base64,${brand.logo_image_base64}`
    : null;
  return (
    <article className="brand-card">
      {logoDataUrl && (
        <div className="brand-card__logo-wrap">
          <img src={logoDataUrl} alt={`${brandName || brand.brand_name} logo`} className="brand-card__logo" />
        </div>
      )}
      <h3 className="brand-card__name">{brandName || brand.brand_name}</h3>
      {brand.brand_tagline && (
        <p className="brand-card__tagline">{brand.brand_tagline}</p>
      )}
      {brand.inspired_by_product && (
        <p className="brand-card__inspired">Inspired by: {brand.inspired_by_product}</p>
      )}
      {brand.brand_values && brand.brand_values.length > 0 && (
        <div className="brand-card__values">
          {brand.brand_values.map((v, i) => (
            <span key={i} className="brand-card__pill">{v}</span>
          ))}
        </div>
      )}
      {brand.brand_story && (
        <div className="brand-card__section">
          <strong>Brand story</strong>
          <p>{brand.brand_story}</p>
        </div>
      )}
      {brand.target_demographic && (
        <div className="brand-card__section">
          <strong>Target demographic</strong>
          <p>{brand.target_demographic}</p>
        </div>
      )}
      {brand.price_positioning && (
        <span className="brand-card__price-badge">{brand.price_positioning}</span>
      )}
      {brand.distribution_strategy && (
        <div className="brand-card__section">
          <strong>Distribution</strong>
          <p>{brand.distribution_strategy}</p>
        </div>
      )}
      {brand.brand_personality && (
        <div className="brand-card__section">
          <strong>Personality</strong>
          <p>{brand.brand_personality}</p>
        </div>
      )}
    </article>
  );
}

function ProductIdeaCard({ product: p }: { product: ProductIdea }) {
  return (
    <article className="product-idea-card">
      <div className="product-idea-card__header">
        <span className="product-idea-card__rank">Concept #{p.rank}</span>
        {p.has_image && (
          <span className="product-idea-card__badge">AI-Generated Concept</span>
        )}
      </div>

      <div className="product-idea-card__image-wrap">
        {p.image_base64 ? (
          <img
            src={`data:image/${p.image_base64_format || 'png'};base64,${p.image_base64}`}
            alt={p.product_name}
            className="product-idea-card__image"
          />
        ) : p.image_url ? (
          <img
            src={p.image_url}
            alt={p.product_name}
            className="product-idea-card__image"
          />
        ) : p.has_image ? (
          <span className="product-idea-card__image-placeholder">Image in PDF</span>
        ) : (
          <span className="product-idea-card__image-placeholder">No image</span>
        )}
      </div>

      <div className="product-idea-card__label">Product</div>
      <div className="product-idea-card__value">{p.product_name}</div>

      {p.estimated_price_usd != null && (
        <div className="product-idea-card__price">${p.estimated_price_usd.toFixed(2)}</div>
      )}

      {p.description && (
        <>
          <div className="product-idea-card__label">Description</div>
          <p className="product-idea-card__description">{p.description}</p>
        </>
      )}

      {p.why_it_would_sell && (
        <>
          <div className="product-idea-card__label">Why it would sell</div>
          <p className="product-idea-card__value">{p.why_it_would_sell}</p>
        </>
      )}

      {p.key_ingredients && p.key_ingredients.length > 0 && (
        <div className="product-idea-card__ingredients">
          <span className="product-idea-card__label">Key ingredients</span>
          <div className="product-idea-card__pills">
            {p.key_ingredients.map((ing, i) => (
              <span key={i} className="product-idea-card__pill">{ing}</span>
            ))}
          </div>
        </div>
      )}

      {p.competitive_advantage && (
        <>
          <div className="product-idea-card__label">Competitive advantage</div>
          <p className="product-idea-card__value">{p.competitive_advantage}</p>
        </>
      )}

      {(p.supporting_trends_intro || (p.supporting_trends && p.supporting_trends.length > 0)) && (
        <>
          <div className="product-idea-card__trends-title">Supporting Trends</div>
          {p.supporting_trends_intro && (
            <p className="product-idea-card__trends-intro">{p.supporting_trends_intro}</p>
          )}
          {p.supporting_trends && p.supporting_trends.length > 0 && (
            <ol className="product-idea-card__trends-list" start={1}>
              {p.supporting_trends.map((trend, i) => {
                const isObj = typeof trend === 'object' && trend !== null && 'title' in trend;
                const t = trend as SupportingTrend;
                return (
                  <li key={i} className="product-idea-card__trend-item">
                    {isObj && t.title ? (
                      <>
                        <strong className="product-idea-card__trend-title">{t.title}</strong>
                        {t.description && <p className="product-idea-card__trend-desc">{t.description}</p>}
                      </>
                    ) : (
                      <span>{typeof trend === 'string' ? trend : (t.title || t.description || '')}</span>
                    )}
                  </li>
                );
              })}
            </ol>
          )}
        </>
      )}
    </article>
  );
}
