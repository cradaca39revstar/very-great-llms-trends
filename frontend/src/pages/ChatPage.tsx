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
  type BrandProposal,
  type MarketProduct,
  type ProductIdea,
  type SupportingTrend,
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
    <div className="chat-layout">
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
  const { report, pdf_url, request_id, execution_time_ms, product_count, brand_name } = data;
  const brand = report.brand_proposal;
  const marketContext = report.market_context ?? [];
  const productIdeas = report.product_ideas ?? [];

  return (
    <div>
      <p className="results-intro">Product Innovation Report</p>
      <div className="results-meta">
        <span>Request ID: {request_id}</span>
        <span>Execution: {execution_time_ms} ms</span>
        <span>Product ideas: {product_count}</span>
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

      {brand && (
        <BrandProposalCard brand={brand} brandName={brand_name || brand.brand_name} />
      )}

      {marketContext.length > 0 && (
        <MarketContextSection products={marketContext} />
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
  const logoDataUrl = brand.logo_image_base64
    ? `data:image/png;base64,${brand.logo_image_base64}`
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

function MarketContextSection({ products }: { products: MarketProduct[] }) {
  const [open, setOpen] = useState(true);
  return (
    <section className="market-context">
      <button
        type="button"
        className="market-context__toggle"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        {open ? '▼' : '▶'} Market Analysis – Top performers used as context
      </button>
      {open && (
        <>
          <p className="market-context__subtitle">
            These top-performing products were analyzed to generate the brand concept.
          </p>
          <div className="market-context__table-wrap">
            <table className="market-context__table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Product</th>
                  <th>Shop</th>
                  <th>Revenue (USD)</th>
                  <th>Growth %</th>
                  <th>Sold</th>
                </tr>
              </thead>
              <tbody>
                {products.map((p, i) => (
                  <tr key={i}>
                    <td>{p.revenue_rank}</td>
                    <td>{p.product_name}</td>
                    <td>{p.shop_name}</td>
                    <td>{p.revenue_usd?.toLocaleString() ?? '—'}</td>
                    <td>{p.mom_growth_pct != null ? `${p.mom_growth_pct}%` : '—'}</td>
                    <td>{p.item_sold != null ? p.item_sold.toLocaleString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
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
            src={`data:image/png;base64,${p.image_base64}`}
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
