import { useState, useEffect } from 'react';
import { fetchProjects, fetchSolutions, fetchImpactDashboard, fetchVerticalSummary, runCalculator, seedData } from './api';

const VERTICALS = [
  { key: 'water', label: '💧 Water', icon: '💧' },
  { key: 'energy', label: '⚡ Energy', icon: '⚡' },
  { key: 'ai_infrastructure', label: '🤖 AI Infra', icon: '🤖' },
  { key: 'food_security', label: '🌾 Food', icon: '🌾' },
  { key: 'education', label: '📚 Education', icon: '📚' },
  { key: 'transport', label: '🚗 Transport', icon: '🚗' },
];

const STATUS_LABELS = {
  planning: '📋 Planning',
  funding: '💰 Funding',
  procurement: '🛒 Procurement',
  construction: '🏗️ Construction',
  operational: '✅ Operational',
};

function formatCurrency(n) {
  if (n >= 1000000) return `$${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `$${(n / 1000).toFixed(0)}K`;
  return `$${n?.toFixed(0) || 0}`;
}

function formatNumber(n) {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n?.toFixed(0) || '0';
}

// ─── Header ───────────────────────────────────────────────────

function Header({ activeTab, setActiveTab }) {
  return (
    <header className="header">
      <div className="header-inner">
        <div className="logo">
          <span className="logo-icon">⚡</span>
          FutureStack
        </div>
        <nav className="nav-tabs">
          {['Dashboard', 'Projects', 'Marketplace', 'Impact', 'Calculator'].map(tab => (
            <button
              key={tab}
              className={`nav-tab ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>
    </header>
  );
}

// ─── Dashboard Tab ────────────────────────────────────────────

function DashboardTab() {
  const [summary, setSummary] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchVerticalSummary().then(data => { setSummary(data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const totals = summary.reduce((acc, v) => ({
    projects: acc.projects + (v.total_projects || 0),
    operational: acc.operational + (v.operational || 0),
    budget: acc.budget + (v.total_budget_usd || 0),
    funded: acc.funded + (v.total_funded_usd || 0),
    beneficiaries: acc.beneficiaries + (v.total_beneficiaries || 0),
  }), { projects: 0, operational: 0, budget: 0, funded: 0, beneficiaries: 0 });

  if (loading) return <div className="loading"><div className="spinner" />Loading dashboard...</div>;

  return (
    <div>
      <div className="hero-stats">
        <div className="stat-card">
          <div className="stat-label">Total Projects</div>
          <div className="stat-value">{totals.projects}</div>
          <div className="stat-sub">{totals.operational} operational</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Funded</div>
          <div className="stat-value">{formatCurrency(totals.funded)}</div>
          <div className="stat-sub">of {formatCurrency(totals.budget)} target</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">People Served</div>
          <div className="stat-value">{formatNumber(totals.beneficiaries)}</div>
          <div className="stat-sub">across all verticals</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Verticals Active</div>
          <div className="stat-value">{summary.filter(v => v.total_projects > 0).length}</div>
          <div className="stat-sub">of 6 verticals</div>
        </div>
      </div>

      <div className="section-header">
        <h2 className="section-title">📊 Vertical Breakdown</h2>
      </div>

      <div className="project-grid">
        {summary.map(v => {
          const vInfo = VERTICALS.find(x => x.key === v.vertical) || { icon: '📦', label: v.vertical };
          const pct = v.total_budget_usd ? ((v.total_funded_usd / v.total_budget_usd) * 100).toFixed(0) : 0;
          return (
            <div className="project-card" key={v.vertical}>
              <div className="project-header">
                <div className={`project-icon ${v.vertical}`}>{vInfo.icon}</div>
                <div>
                  <div className="project-name">{vInfo.label}</div>
                  <div className="project-location">{v.total_projects} projects · {v.total_beneficiaries.toLocaleString()} people</div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                <span className={`status-badge ${v.operational > 0 ? 'operational' : 'planning'}`}>
                  <span className="status-dot" />{v.operational} operational
                </span>
              </div>
              <div className="funding-bar-outer">
                <div className="funding-bar-inner" style={{ width: `${Math.min(pct, 100)}%` }} />
              </div>
              <div className="funding-label">
                <span>{formatCurrency(v.total_funded_usd)} funded</span>
                <strong>{pct}%</strong>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Projects Tab ─────────────────────────────────────────────

function ProjectsTab() {
  const [projects, setProjects] = useState([]);
  const [filter, setFilter] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchProjects(filter).then(data => { setProjects(data.projects || []); setLoading(false); });
  }, [filter]);

  return (
    <div>
      <div className="vertical-chips">
        <button className={`vertical-chip ${!filter ? 'active' : ''}`} onClick={() => setFilter(null)} style={!filter ? { background: 'var(--gradient-primary)', borderColor: 'transparent' } : {}}>All</button>
        {VERTICALS.map(v => (
          <button key={v.key} className={`vertical-chip ${filter === v.key ? 'active' : ''}`} data-vertical={v.key} onClick={() => setFilter(v.key)}>{v.label}</button>
        ))}
      </div>

      {loading ? <div className="loading"><div className="spinner" />Loading projects...</div> : (
        <div className="project-grid">
          {projects.map(p => {
            const vInfo = VERTICALS.find(x => x.key === p.vertical) || { icon: '📦' };
            return (
              <div className="project-card" key={p.id}>
                <div className="project-header">
                  <div className={`project-icon ${p.vertical}`}>{vInfo.icon}</div>
                  <div>
                    <div className="project-name">{p.name}</div>
                    <div className="project-location">{p.location} {p.country ? `· ${p.country}` : ''}</div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                  <span className={`status-badge ${p.status}`}><span className="status-dot" />{STATUS_LABELS[p.status] || p.status}</span>
                </div>
                <div className="funding-bar-outer">
                  <div className="funding-bar-inner" style={{ width: `${Math.min(p.funding_pct || 0, 100)}%` }} />
                </div>
                <div className="funding-label">
                  <span>{formatCurrency(p.funded_usd)} of {formatCurrency(p.target_budget_usd)}</span>
                  <strong>{p.funding_pct?.toFixed(0) || 0}%</strong>
                </div>
                {p.beneficiary_count > 0 && <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 8 }}>👥 {p.beneficiary_count.toLocaleString()} people served</div>}
              </div>
            );
          })}
          {projects.length === 0 && <div style={{ color: 'var(--text-muted)', padding: 40 }}>No projects found. Seed data first.</div>}
        </div>
      )}
    </div>
  );
}

// ─── Marketplace Tab ──────────────────────────────────────────

function MarketplaceTab() {
  const [solutions, setSolutions] = useState([]);
  const [filter, setFilter] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchSolutions(filter).then(data => { setSolutions(data.solutions || []); setLoading(false); });
  }, [filter]);

  return (
    <div>
      <div className="vertical-chips">
        <button className={`vertical-chip ${!filter ? 'active' : ''}`} onClick={() => setFilter(null)} style={!filter ? { background: 'var(--gradient-primary)', borderColor: 'transparent' } : {}}>All Solutions</button>
        {VERTICALS.map(v => (
          <button key={v.key} className={`vertical-chip ${filter === v.key ? 'active' : ''}`} data-vertical={v.key} onClick={() => setFilter(v.key)}>{v.label}</button>
        ))}
      </div>

      {loading ? <div className="loading"><div className="spinner" />Loading marketplace...</div> : (
        <div className="solution-grid">
          {solutions.map(s => {
            const vInfo = VERTICALS.find(x => x.key === s.vertical) || { icon: '📦' };
            return (
              <div className="solution-card" key={s.id}>
                <span className="solution-type">{s.solution_type}</span>
                <div className="solution-name">{vInfo.icon} {s.name}</div>
                <div className="solution-price">
                  {s.price_usd ? formatCurrency(s.price_usd) : 'Quote Required'}
                  {s.price_model !== 'fixed' && <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}> / {s.price_model}</span>}
                </div>
                <div className="solution-meta">
                  {s.impact_rating && <span className="rating">★ {s.impact_rating}</span>}
                  {s.review_count > 0 && <span>({s.review_count} reviews)</span>}
                  {s.verified && <span className="verified-badge">✓ Verified</span>}
                </div>
              </div>
            );
          })}
          {solutions.length === 0 && <div style={{ color: 'var(--text-muted)', padding: 40 }}>No solutions listed yet.</div>}
        </div>
      )}
    </div>
  );
}

// ─── Impact Tab ───────────────────────────────────────────────

function ImpactTab() {
  const [impact, setImpact] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchImpactDashboard().then(data => { setImpact(data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading"><div className="spinner" />Loading impact data...</div>;
  if (!impact) return <div className="loading">No impact data available.</div>;

  return (
    <div>
      <div className="hero-stats">
        <div className="stat-card">
          <div className="stat-label">Operational Projects</div>
          <div className="stat-value">{impact.total_projects || 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">People Benefited</div>
          <div className="stat-value">{formatNumber(impact.total_beneficiaries || 0)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Funded</div>
          <div className="stat-value">{formatCurrency(impact.total_funded_usd || 0)}</div>
        </div>
      </div>

      <div className="section-header">
        <h2 className="section-title">📈 Live Impact Metrics</h2>
      </div>

      <div className="impact-grid">
        {Object.entries(impact.metrics || {}).map(([key, data]) => (
          <div className={`impact-card ${key.includes('liter') ? 'water' : key.includes('kwh') ? 'energy' : 'food'}`} key={key}>
            <div className="stat-label">{key.replace(/_/g, ' ')}</div>
            <div className="impact-value">{formatNumber(data.total)}</div>
            <div className="impact-unit">
              avg: {formatNumber(data.average)} · peak: {formatNumber(data.peak)}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>{data.readings} readings</div>
          </div>
        ))}
        {Object.keys(impact.metrics || {}).length === 0 && <div style={{ color: 'var(--text-muted)', padding: 40, gridColumn: '1 / -1' }}>No metrics recorded yet. Seed data first.</div>}
      </div>
    </div>
  );
}

// ─── Calculator Tab ───────────────────────────────────────────

function CalculatorTab() {
  const [calcType, setCalcType] = useState('energy');
  const [population, setPopulation] = useState(1000);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const CALC_CONFIGS = {
    water: { endpoint: 'purification', label: 'Water Purification Plant', paramName: 'population' },
    energy: { endpoint: 'solar', label: 'Solar Microgrid', paramName: 'households' },
    food: { endpoint: 'vertical-farm', label: 'Vertical Farm', paramName: 'population' },
    education: { endpoint: 'learning-network', label: 'Learning Network', paramName: 'student_population' },
    transport: { endpoint: 'shuttle-fleet', label: 'EV Shuttle Fleet', paramName: 'daily_passengers' },
  };

  const config = CALC_CONFIGS[calcType] || CALC_CONFIGS.energy;

  async function handleCalculate() {
    setLoading(true);
    const data = { [config.paramName]: parseInt(population) };
    if (calcType === 'transport') data.route_km = 15;
    try {
      const res = await runCalculator(calcType === 'food' ? 'food' : calcType, config.endpoint, data);
      setResult(res);
    } catch { setResult({ error: 'Calculation failed' }); }
    setLoading(false);
  }

  return (
    <div className="calc-panel">
      <div className="section-header">
        <h2 className="section-title">🧮 Infrastructure Sizing Calculator</h2>
      </div>

      <div className="vertical-chips" style={{ marginBottom: 24 }}>
        {Object.entries(CALC_CONFIGS).map(([key, cfg]) => {
          const vInfo = VERTICALS.find(x => x.key === key || x.key === key + '_security');
          return (
            <button key={key} className={`vertical-chip ${calcType === key ? 'active' : ''}`} data-vertical={key === 'food' ? 'food_security' : key} onClick={() => { setCalcType(key); setResult(null); }}>
              {vInfo?.icon || '📦'} {cfg.label}
            </button>
          );
        })}
      </div>

      <div className="calc-form">
        <div className="form-group">
          <label>{config.paramName === 'households' ? 'Number of Households' : config.paramName === 'daily_passengers' ? 'Daily Passengers' : config.paramName === 'student_population' ? 'Student Population' : 'Population'}</label>
          <input type="number" value={population} onChange={e => setPopulation(e.target.value)} min="1" />
        </div>
        <div className="form-group" style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button className="btn-primary" onClick={handleCalculate} disabled={loading}>
            {loading ? 'Calculating...' : `Size ${config.label}`}
          </button>
        </div>
      </div>

      {result && (
        <div className="calc-results">
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

// ─── App ──────────────────────────────────────────────────────

export default function App() {
  const [activeTab, setActiveTab] = useState('Dashboard');
  const [seeded, setSeeded] = useState(false);

  useEffect(() => {
    // Auto-seed on first load
    if (!seeded) {
      seedData().then(() => setSeeded(true)).catch(() => {});
    }
  }, []);

  return (
    <div className="app">
      <Header activeTab={activeTab} setActiveTab={setActiveTab} />
      <main className="main-content">
        {activeTab === 'Dashboard' && <DashboardTab />}
        {activeTab === 'Projects' && <ProjectsTab />}
        {activeTab === 'Marketplace' && <MarketplaceTab />}
        {activeTab === 'Impact' && <ImpactTab />}
        {activeTab === 'Calculator' && <CalculatorTab />}
      </main>
    </div>
  );
}
