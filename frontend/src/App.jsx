import { useEffect, useRef, useState } from 'react'
import { api } from './lib/api'
import GradientWaves from './components/GradientWaves'

function App() {
  const [tab, setTab] = useState('overview')
  const [bootstrapped, setBootstrapped] = useState(null)
  const [watchlistData, setWatchlistData] = useState(null)
  const [changesData, setChangesData] = useState(null)
  const [timelineData, setTimelineData] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [simulatedPreset, setSimulatedPreset] = useState(null)
  const [ackLoading, setAckLoading] = useState(false)
  const [drawerSymbol, setDrawerSymbol] = useState(null)
  const [highlightedSection, setHighlightedSection] = useState(null)
  const [error, setError] = useState('')
  const [actionError, setActionError] = useState('')

  function scrollToSection(sectionId) {
    if (tab !== 'overview') {
      setTab('overview')
    }
    setHighlightedSection(sectionId)
    setTimeout(() => {
      const el = document.getElementById(sectionId)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }, 50)
    setTimeout(() => {
      setHighlightedSection(null)
    }, 2000)
  }

  useEffect(() => {
    let active = true

    async function bootstrap() {
      try {
        setLoading(true)
        setError('')
        const demo = await api.bootstrapDemo()
        if (!active) return
        setBootstrapped(demo)
        await loadDashboard(demo.watchlist.id, active, null)
      } catch (loadError) {
        if (!active) return
        setError(loadError.message)
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    bootstrap()
    return () => {
      active = false
    }
  }, [])

  async function loadDashboard(watchlistId, active = true, preset = simulatedPreset) {
    setRefreshing(true)
    setActionError('')
    try {
      const [watchlist, changes, timeline] = await Promise.all([
        api.getWatchlist(watchlistId),
        api.getChanges(watchlistId, preset),
        api.getTimeline(watchlistId, preset),
      ])
      if (!active) return
      setWatchlistData(watchlist)
      setChangesData(changes)
      setTimelineData(timeline.events || [])
    } catch (loadError) {
      if (!active) return
      setActionError(loadError.message)
    } finally {
      if (active) {
        setRefreshing(false)
      }
    }
  }

  async function handleSelectPreset(preset) {
    setSimulatedPreset(preset)
    if (bootstrapped) {
      await loadDashboard(bootstrapped.watchlist.id, true, preset)
    }
  }

  async function handleClearPreset() {
    setSimulatedPreset(null)
    if (bootstrapped) {
      await loadDashboard(bootstrapped.watchlist.id, true, null)
    }
  }

  async function handleAddStockSymbol(symbol) {
    if (!bootstrapped) return
    try {
      setActionError('')
      await api.addStock(bootstrapped.watchlist.id, { symbol })
      await loadDashboard(bootstrapped.watchlist.id, true, simulatedPreset)
      setTab('watchlist')
    } catch (addError) {
      setActionError(addError.message)
    }
  }

  async function handleRemoveStock(symbol) {
    if (!bootstrapped) return
    try {
      setActionError('')
      await api.deleteStock(bootstrapped.watchlist.id, symbol)
      if (drawerSymbol === symbol) {
        setDrawerSymbol(null)
      }
      await loadDashboard(bootstrapped.watchlist.id, true, simulatedPreset)
    } catch (removeError) {
      setActionError(removeError.message)
    }
  }

  async function handleAcknowledge() {
    if (!bootstrapped || ackLoading) return
    try {
      setAckLoading(true)
      setActionError('')
      await api.acknowledgeWatchlist(bootstrapped.watchlist.id)
      setSimulatedPreset(null)
      await loadDashboard(bootstrapped.watchlist.id, true, null)
    } catch (ackError) {
      setActionError(ackError.message)
    } finally {
      setAckLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="start-screen-container">
        <GradientWaves
          color1="#F5F0EB"
          color2="#E8DFC9"
          color3="#C9D6C9"
          color4="#D6C8C7"
          speed={0.5}
          amplitude={0.65}
          interactive={true}
        />
        <div className="start-screen-content">
          <p className="start-eyebrow">SMART MARKET WATCHLIST</p>
          <h1 className="start-title">Preparing your market update</h1>
          <p className="start-subtitle">
            Fetching the latest market data and getting your watchlist ready.
          </p>
          <div className="start-progress">
            <div className="start-progress-bar" />
          </div>
        </div>
      </div>
    )
  }

  if (error || !bootstrapped || !watchlistData || !changesData) {
    return (
      <div className="app-shell">
        <main className="frame frame-loading">
          <div className="loading-card error-card">
            <p className="eyebrow">Connection issue</p>
            <h1>We couldn&apos;t load the watchlist.</h1>
            <p>{error || 'Unknown error.'}</p>
          </div>
        </main>
      </div>
    )
  }

  const { watchlist } = bootstrapped
  const stocks = watchlistData.stocks || []
  const groups = changesData.groups || {}

  return (
    <div className="app-shell">
      <main className="frame">
        <header className="topbar">
          <div>
            <p className="eyebrow">Smart Market Watchlist</p>
            <h1>{greeting()}, what did you miss?</h1>
            <p className="subtle">
              What I Missed for {bootstrapped.user.username} · Last checked {changesData.elapsed_text || formatElapsed(changesData.last_checked_at)}
              {simulatedPreset ? ` (Simulated: ${simulatedPreset.replace('_', ' ')})` : ''}.
            </p>
          </div>
          <div className="topbar-actions">
            <button className="button ghost" onClick={() => loadDashboard(watchlist.id)} disabled={refreshing || ackLoading}>
              {refreshing ? 'Refreshing...' : 'Refresh'}
            </button>
            <button className="button primary" onClick={handleAcknowledge} disabled={ackLoading || refreshing}>
              {ackLoading ? 'Saving...' : 'Mark as seen'}
            </button>
          </div>
        </header>

        <details className="demo-panel">
          <summary className="demo-summary">
            <span className="demo-badge">DEV / DEMO</span>
            <strong>Test against checkpoints</strong>
            <span className="subtle">— Simulate returning after different amounts of time.</span>
          </summary>
          <div className="demo-content">
            <p className="subtle">
              Select a checkpoint preset to test how the change engine calculates market movements and elapsed time using real yfinance data:
            </p>
            <div className="demo-buttons">
              <button
                className={simulatedPreset === 'just_now' ? 'button secondary active' : 'button secondary'}
                onClick={() => handleSelectPreset('just_now')}
              >
                Just now
              </button>
              <button
                className={simulatedPreset === '1h_ago' ? 'button secondary active' : 'button secondary'}
                onClick={() => handleSelectPreset('1h_ago')}
              >
                1 hour ago
              </button>
              <button
                className={simulatedPreset === '1d_ago' ? 'button secondary active' : 'button secondary'}
                onClick={() => handleSelectPreset('1d_ago')}
              >
                1 day ago
              </button>
              <button
                className={simulatedPreset === '3d_ago' ? 'button secondary active' : 'button secondary'}
                onClick={() => handleSelectPreset('3d_ago')}
              >
                3 days ago
              </button>
              <button
                className={simulatedPreset === '28aug_demo' ? 'button secondary active' : 'button secondary'}
                onClick={() => handleSelectPreset('28aug_demo')}
              >
                28 Aug demo
              </button>
              {simulatedPreset ? (
                <button className="button ghost danger" onClick={handleClearPreset}>
                  Return to live checkpoint
                </button>
              ) : null}
            </div>
            {simulatedPreset ? (
              <p className="demo-banner">
                ⚠️ Currently testing with simulated checkpoint: <strong>{simulatedPreset.replace('_', ' ')}</strong>. Real DB checkpoint remains unchanged.
              </p>
            ) : null}
          </div>
        </details>

        <section className="hero-strip">
          <div
            className="hero-card"
            onClick={() => scrollToSection('section-needs-attention')}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && scrollToSection('section-needs-attention')}
          >
            <p className="card-label">Needs your attention</p>
            <strong>{groups.needs_attention?.length || 0}</strong>
            <span>Meaningful moves since you last checked.</span>
          </div>
          <div
            className="hero-card"
            onClick={() => scrollToSection('section-worth-watching')}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && scrollToSection('section-worth-watching')}
          >
            <p className="card-label">Worth watching</p>
            <strong>{groups.worth_watching?.length || 0}</strong>
            <span>Stocks moving enough to keep on your radar.</span>
          </div>
          <div
            className="hero-card"
            onClick={() => scrollToSection('section-all-quiet')}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && scrollToSection('section-all-quiet')}
          >
            <p className="card-label">All quiet</p>
            <strong>{groups.all_quiet?.length || 0}</strong>
            <span>Names that mostly moved with the market.</span>
          </div>
        </section>

        <nav className="tabs">
          <button className={tab === 'overview' ? 'tab active' : 'tab'} onClick={() => setTab('overview')}>
            What I Missed
          </button>
          <button className={tab === 'watchlist' ? 'tab active' : 'tab'} onClick={() => setTab('watchlist')}>
            Watchlist ({stocks.length})
          </button>
        </nav>

        {actionError ? <section className="banner error">{actionError}</section> : null}

        {tab === 'overview' ? (
          <div className="content-grid">
            <section className="main-column">
              <ChangeSection
                id="section-needs-attention"
                title="Needs Your Attention"
                subtitle="The most meaningful moves since your checkpoint."
                changes={groups.needs_attention || []}
                onOpenDrawer={(symbol) => setDrawerSymbol(symbol)}
                isHighlighted={highlightedSection === 'section-needs-attention'}
              />
              <ChangeSection
                id="section-worth-watching"
                title="Worth Watching"
                subtitle="Not urgent, but worth a closer look."
                changes={groups.worth_watching || []}
                onOpenDrawer={(symbol) => setDrawerSymbol(symbol)}
                isHighlighted={highlightedSection === 'section-worth-watching'}
              />
              <ChangeSection
                id="section-all-quiet"
                title="All Quiet"
                subtitle="Stocks that mostly moved with the market."
                changes={groups.all_quiet || []}
                onOpenDrawer={(symbol) => setDrawerSymbol(symbol)}
                isHighlighted={highlightedSection === 'section-all-quiet'}
              />
            </section>

            <aside className="side-column">
              <section className="panel-card timeline-panel">
                <div className="panel-head">
                  <div>
                    <p className="card-label">Timeline</p>
                    <h2>Notable moments</h2>
                  </div>
                </div>
                {timelineData.length ? (
                  <div className="timeline">
                    {timelineData.slice(0, 10).map((event) => (
                      <article className="timeline-item" key={`${event.symbol}-${event.date}`}>
                        <span className={`timeline-dot ${event.direction}`}></span>
                        <div>
                          <p className="timeline-date">{formatDate(event.date)}</p>
                          <strong>{event.display_name || event.symbol}</strong>
                          <span className="ticker-sublabel">{event.symbol}</span>
                          <p>{event.label}</p>
                          <button
                            className="view-detail-btn"
                            onClick={() => setDrawerSymbol(event.symbol)}
                            style={{ marginTop: '6px' }}
                          >
                            View details <span className="arrow-icon">&rarr;</span>
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="subtle">No standout moves during the away period yet.</p>
                )}
              </section>
            </aside>
          </div>
        ) : (
          <div className="content-grid">
            <section className="main-column">
              <section className="panel-card">
                <div className="panel-head">
                  <div>
                    <p className="card-label">Watchlist</p>
                    <h2>Your monitored stocks</h2>
                  </div>
                </div>
                {stocks.length ? (
                  <div className="stock-table">
                    {stocks.map((stock) => (
                      <article className="stock-row" key={stock.symbol}>
                        <div>
                          <strong>{stock.display_name || stock.symbol}</strong>
                          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '2px' }}>
                            <span className="ticker-sublabel">{stock.symbol}</span>
                            {stock.sector ? <span className="sector-tag">{stock.sector}</span> : null}
                          </div>
                          <p>{stock.latest_price_date ? `Latest market data · ${formatDate(stock.latest_price_date)}` : 'No market data yet'}</p>
                        </div>
                        <div>
                          <span className="stock-value">{formatCurrency(stock.latest_price)}</span>
                          <p className={toneForValue(stock.day_change_percent)}>{formatPercent(stock.day_change_percent)}</p>
                        </div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button className="button ghost" onClick={() => setDrawerSymbol(stock.symbol)}>
                            View details <span className="arrow-icon">&rarr;</span>
                          </button>
                          <button className="button ghost danger" onClick={() => handleRemoveStock(stock.symbol)}>
                            Remove
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (

                  <div className="empty-state">
                    <strong>Your watchlist is empty</strong>
                    <p>Search for a company on the right or pick a popular stock below to start tracking what changed while you were away.</p>
                    <div className="quick-add-wrap">
                      {['Reliance', 'Infosys', 'TCS', 'HDFC Bank', 'Tata Motors'].map((name) => (
                        <button
                          key={name}
                          className="quick-add-pill"
                          onClick={() => {
                            const symbolMap = {
                              Reliance: 'RELIANCE.NS',
                              Infosys: 'INFY.NS',
                              TCS: 'TCS.NS',
                              'HDFC Bank': 'HDFCBANK.NS',
                              'Tata Motors': 'TATAMOTORS.NS',
                            }
                            handleAddStockSymbol(symbolMap[name])
                          }}
                        >
                          + {name}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            </section>

            <aside className="side-column">
              <SearchAddStock
                onAddStock={handleAddStockSymbol}
                watchlistStocks={stocks}
                actionError={actionError}
                setActionError={setActionError}
              />
            </aside>
          </div>
        )}
      </main>

      {/* RIGHT-SIDE STOCK DETAIL DRAWER */}
      {drawerSymbol ? (
        <StockDetailDrawer
          symbol={drawerSymbol}
          watchlistId={watchlist.id}
          simulatedPreset={simulatedPreset}
          onClose={() => setDrawerSymbol(null)}
        />
      ) : null}
    </div>
  )
}

function ChangeSection({ id, title, subtitle, changes, onOpenDrawer, isHighlighted }) {
  return (
    <section id={id} className={`panel-card ${isHighlighted ? 'section-highlight-pulse' : ''}`}>
      <div className="panel-head">
        <div>
          <p className="card-label">{title}</p>
          <h2>{subtitle}</h2>
        </div>
      </div>
      {changes.length ? (
        <div className="change-list">
          {changes.map((change) => (
            <article className="change-card" key={change.symbol}>
              <div className="change-head">
                <div>
                  <strong>{change.display_name || change.symbol}</strong>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '2px' }}>
                    <span className="ticker-sublabel">{change.symbol}</span>
                    {change.sector ? <span className="sector-tag">{change.sector}</span> : null}
                  </div>
                </div>
                <span className={`pill ${change.classification.toLowerCase().replaceAll('_', '-')}`}>
                  {change.classification.replaceAll('_', ' ')}
                </span>
              </div>
              <div className="change-grid">
                <Metric label="Latest price" value={formatCurrency(change.latest_price)} />
                <Metric
                  label="Since last check"
                  value={formatPercent(change.stock_return)}
                  tone={toneForValue(change.stock_return)}
                />
                <Metric
                  label="Vs NIFTY"
                  value={formatPercent(change.relative_performance)}
                  tone={toneForValue(change.relative_performance)}
                />
              </div>
              <p className="compact-why" style={{ margin: '10px 0 0', fontSize: '0.88rem' }}>
                {change.why.summary}
              </p>
              <button className="view-detail-btn" onClick={() => onOpenDrawer(change.symbol)}>
                View details <span className="arrow-icon">&rarr;</span>
              </button>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState title={`No ${title.toLowerCase()} right now`} body="That bucket is clear at the moment." />
      )}
    </section>
  )
}

function SearchAddStock({ onAddStock, watchlistStocks = [], actionError, setActionError }) {
  const [query, setQuery] = useState('')
  const [selectedSector, setSelectedSector] = useState('All')
  const [results, setResults] = useState([])
  const [isSearching, setIsSearching] = useState(false)
  const [preview, setPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  const addedSymbolSet = new Set((watchlistStocks || []).map((s) => s.symbol))

  const SECTORS = [
    'All',
    'Banking',
    'Financial Services',
    'Technology',
    'Automotive',
    'Pharma',
    'Energy',
    'FMCG',
    'Metals',
    'Telecom',
    'Construction',
  ]

  useEffect(() => {
    let active = true

    async function fetchSearch() {
      setIsSearching(true)
      try {
        const res = await api.searchStocks(query, selectedSector)
        if (active) {
          setResults(res.results || [])
        }
      } catch (err) {
        if (active) setResults([])
      } finally {
        if (active) setIsSearching(false)
      }
    }

    const timer = setTimeout(fetchSearch, 150)
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [query, selectedSector])

  async function handleSelectResult(item) {
    if (addedSymbolSet.has(item.symbol)) return
    setPreviewLoading(true)
    setActionError('')
    try {
      const data = await api.previewStock(item.symbol)
      setPreview(data)
    } catch (err) {
      setActionError(err.message)
      setPreview(null)
    } finally {
      setPreviewLoading(false)
    }
  }

  async function handleQuickAdd(symbol) {
    if (addedSymbolSet.has(symbol)) return
    await onAddStock(symbol)
    setPreview(null)
  }

  async function handleAdd() {
    if (!preview) return
    await onAddStock(preview.symbol)
    setPreview(null)
  }

  return (
    <section className="panel-card add-panel">
      <div className="panel-head">
        <div>
          <p className="card-label">Add stock</p>
          <h2>Search &amp; browse stocks</h2>
        </div>
      </div>
      <div className="add-form">
        <label htmlFor="stock-search">Search by name, ticker, or sector</label>
        <div className="search-container">
          <input
            id="stock-search"
            type="text"
            placeholder="e.g. Tata, INFY, Banking, Tech..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Sector Browsing Filter Pills */}
      <div className="sector-browse-wrap" style={{ marginTop: '14px' }}>
        <span className="subtle" style={{ width: '100%', fontSize: '0.78rem', display: 'block', marginBottom: '6px' }}>
          Browse by sector:
        </span>
        <div className="quick-add-wrap" style={{ marginTop: '0' }}>
          {SECTORS.map((sec) => (
            <button
              key={sec}
              className={`quick-add-pill ${selectedSector === sec ? 'active' : ''}`}
              onClick={() => setSelectedSector(sec)}
            >
              {sec}
            </button>
          ))}
        </div>
      </div>

      {/* Results List */}
      <div style={{ marginTop: '18px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <span className="ticker-sublabel" style={{ fontWeight: 600 }}>
            {selectedSector !== 'All' ? `${selectedSector} Stocks` : 'Available Stocks'} ({results.length})
          </span>
          {isSearching ? <span className="subtle" style={{ fontSize: '0.75rem' }}>Searching...</span> : null}
        </div>

        {results.length ? (
          <div className="search-results-list" style={{ display: 'grid', gap: '8px', maxHeight: '280px', overflowY: 'auto', paddingRight: '4px' }}>
            {results.map((item) => {
              const isAdded = addedSymbolSet.has(item.symbol)
              return (
                <div
                  key={item.symbol}
                  className="search-item-row"
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '10px 14px',
                    borderRadius: '16px',
                    background: 'var(--surface-soft)',
                    border: '1px solid var(--border)',
                  }}
                >
                  <div style={{ cursor: isAdded ? 'default' : 'pointer' }} onClick={() => !isAdded && handleSelectResult(item)}>
                    <strong style={{ fontSize: '0.92rem', color: isAdded ? 'var(--muted)' : 'var(--text)' }}>
                      {item.display_name}
                    </strong>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '2px' }}>
                      <span className="ticker-sublabel">{item.symbol}</span>
                      <span className="sector-tag">{item.sector}</span>
                    </div>
                  </div>

                  {isAdded ? (
                    <span
                      style={{
                        fontSize: '0.78rem',
                        fontWeight: 600,
                        color: 'var(--positive)',
                        background: 'var(--positive-soft)',
                        padding: '4px 10px',
                        borderRadius: '999px',
                        userSelect: 'none',
                      }}
                    >
                      Added ✓
                    </span>
                  ) : (
                    <button
                      className="button ghost"
                      style={{ padding: '6px 14px', fontSize: '0.82rem' }}
                      onClick={() => handleQuickAdd(item.symbol)}
                    >
                      + Add
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        ) : (
          <p className="subtle" style={{ margin: '12px 0 0' }}>No matching stocks found for &quot;{query || selectedSector}&quot;.</p>
        )}
      </div>

      {previewLoading ? (
        <p className="subtle" style={{ marginTop: '16px' }}>Fetching market preview...</p>
      ) : preview ? (
        preview.has_data ? (
          <div className="preview-card">
            <div className="preview-head">
              <div>
                <strong>{preview.display_name || preview.symbol}</strong>
                <span className="ticker-sublabel">{preview.symbol}</span>
              </div>
              <span className={toneForValue(preview.day_change_percent)}>
                {formatPercent(preview.day_change_percent)}
              </span>
            </div>
            <p className="preview-price">{formatCurrency(preview.latest_price)}</p>
            <p className="subtle">Latest market date {formatDate(preview.latest_price_date)}</p>
            <TinySparkline points={preview.trend} />
            <button className="button primary full" onClick={handleAdd}>
              Add to watchlist
            </button>
          </div>
        ) : (
          <EmptyState
            title="No market data available"
            body="That symbol did not return usable market data. Try searching for a valid company name."
          />
        )
      ) : null}
    </section>
  )
}

function StockDetailDrawer({ symbol, watchlistId, simulatedPreset, onClose }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [closing, setClosing] = useState(false)
  const [showRecentHistory, setShowRecentHistory] = useState(false)

  const handleClose = () => {
    if (closing) return
    setClosing(true)
    setTimeout(() => {
      onClose()
    }, 240)
  }

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        handleClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [closing])

  useEffect(() => {
    let active = true

    async function fetchDetail() {
      try {
        setLoading(true)
        setError('')
        const data = await api.getStockDetail(symbol, watchlistId, simulatedPreset)
        if (active) setDetail(data)
      } catch (err) {
        if (active) setError(err.message)
      } finally {
        if (active) setLoading(false)
      }
    }

    fetchDetail()
    return () => {
      active = false
    }
  }, [symbol, watchlistId, simulatedPreset])

  return (
    <div className={`drawer-overlay ${closing ? 'closing' : ''}`} onClick={handleClose}>
      <div className={`drawer-panel ${closing ? 'closing' : ''}`} onClick={(e) => e.stopPropagation()}>
        <header className="drawer-header">
          <div className="drawer-title-group">
            <h2>{detail?.display_name || symbol}</h2>
            <div className="drawer-badges">
              <span className="ticker-sublabel">{symbol}</span>
              {detail?.sector ? <span className="sector-tag">{detail.sector}</span> : null}
            </div>
          </div>
          <button className="close-drawer-btn" onClick={handleClose} aria-label="Close drawer">
            &times;
          </button>
        </header>

        {loading ? (
          <div className="drawer-body">
            <p className="subtle">Loading detailed insights...</p>
          </div>
        ) : error ? (
          <div className="drawer-body">
            <div className="empty-state">
              <strong>Could not load detail</strong>
              <p>{error}</p>
            </div>
          </div>
        ) : detail ? (
          <div className="drawer-body">
            {/* Dual Timestamps Card */}
            <div className="volume-activity-box drawer-animate-item">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="volume-item">
                  <span style={{ fontSize: '0.78rem', color: 'var(--muted)', fontWeight: 600 }}>🕒 LAST CHECKED</span>
                  <strong style={{ fontSize: '0.92rem' }}>
                    {formatDateTime(detail.checkpoint_at || detail.assessment?.user_checkpoint_at)}
                  </strong>
                  <span style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>{detail.elapsed_text}</span>
                </div>
                <div className="volume-item">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.78rem', color: 'var(--muted)', fontWeight: 600 }}>📈 LATEST MARKET DATA</span>
                    {detail.recent_history?.length ? (
                      <button
                        type="button"
                        onClick={() => setShowRecentHistory(!showRecentHistory)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: 'var(--accent, #594B43)',
                          fontSize: '0.72rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          padding: 0,
                          textDecoration: 'underline',
                        }}
                      >
                        {showRecentHistory ? 'Hide history ↑' : 'View recent history →'}
                      </button>
                    ) : null}
                  </div>
                  <strong style={{ fontSize: '0.92rem' }}>
                    {formatDateTime(detail.assessment?.latest_market_timestamp || detail.latest_price_date)}
                  </strong>
                  <span style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
                    {detail.market_status?.status_text || 'NSE Equities'}
                  </span>
                </div>
              </div>
              {detail.assessment?.checkpoint_after_latest_data || !detail.market_status?.is_open ? (
                <div style={{ borderTop: '1px solid var(--border)', paddingTop: '10px', marginTop: '6px' }}>
                  <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--muted)' }}>
                    🔒 <strong>Market status:</strong> Market closed — no new NSE trading session since your last check.
                  </p>
                </div>
              ) : null}
            </div>

            {/* Expandable Recent Market History Box */}
            {showRecentHistory && detail.recent_history?.length ? (
              <div
                className="recent-history-box drawer-animate-item"
                style={{
                  marginTop: '10px',
                  padding: '14px 16px',
                  background: 'rgba(253, 252, 250, 0.95)',
                  borderRadius: '10px',
                  border: '1px solid var(--border)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontSize: '0.78rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--color-text-secondary)' }}>
                    Recent Market History
                  </span>
                  <span className="subtle" style={{ fontSize: '0.75rem' }}>Last 7 trading sessions</span>
                </div>
                <MiniLineChart series={detail.recent_history} />
                <p className="subtle" style={{ margin: '6px 0 0', fontSize: '0.75rem' }}>
                  Price trend from {detail.recent_history[0]?.date} to {detail.recent_history.at(-1)?.date} (independent of checkpoint).
                </p>
              </div>
            ) : null}

            {/* Header Metrics */}
            <div className="change-grid drawer-animate-item">
              <Metric label="Latest price" value={formatCurrency(detail.latest_price)} />
              <Metric
                label="Day change"
                value={formatPercent(detail.day_change_percent)}
                tone={toneForValue(detail.day_change_percent)}
              />
              <Metric
                label="Away movement"
                value={formatPercent(detail.assessment?.stock_return)}
                tone={toneForValue(detail.assessment?.stock_return)}
              />
            </div>

            {/* Section 1: Away Period Performance */}
            <div className="drawer-section drawer-animate-item">
              <h3 className="drawer-section-title">Away Period Performance</h3>
              {detail.series?.length ? (
                <MiniLineChart series={detail.series} />
              ) : (
                <div
                  className="chart-empty-state"
                  style={{
                    padding: '20px 16px',
                    textAlign: 'center',
                    background: 'rgba(253, 252, 250, 0.55)',
                    borderRadius: '10px',
                    border: '1px dashed var(--color-border)',
                    margin: '12px 0 16px',
                  }}
                >
                  <p style={{ margin: 0, fontWeight: 600, color: 'var(--color-text-primary)', fontSize: '0.88rem' }}>
                    No market movement since your last check
                  </p>
                  <p className="subtle" style={{ margin: '4px 0 0', fontSize: '0.78rem' }}>
                    Latest available market data is from before your checkpoint.
                  </p>
                </div>
              )}
              <dl className="metric-grid">
                <Metric label="Stock move" value={formatPercent(detail.assessment?.stock_return)} tone={toneForValue(detail.assessment?.stock_return)} />
                <Metric
                  label="NIFTY move"
                  value={formatPercent(detail.assessment?.nifty_return)}
                  tone={toneForValue(detail.assessment?.nifty_return)}
                />
                <Metric
                  label="Vs NIFTY"
                  value={formatPercent(detail.assessment?.relative_performance)}
                  tone={toneForValue(detail.assessment?.relative_performance)}
                />
              </dl>
              <div className="why-card">
                <strong>Why you&apos;re seeing this:</strong>
                <p style={{ margin: '6px 0 0' }}>{detail.why?.summary}</p>
                {detail.assessment?.unusualness_z !== null && detail.assessment?.unusualness_z !== undefined ? (
                  <p className="subtle" style={{ fontSize: '0.78rem', marginTop: '6px' }}>
                    Statistical unusualness score: <strong>{formatNumber(detail.assessment.unusualness_z)} z</strong>
                  </p>
                ) : null}
              </div>
            </div>

            {/* Section 2: Volume Trading Activity */}
            <div className="drawer-section drawer-animate-item">
              <h3 className="drawer-section-title">Trading Activity</h3>
              <div className="volume-activity-box">
                <div className="activity-header">
                  <strong>Volume Stats</strong>
                  {detail.volume_metrics?.activity_ratio ? (
                    <span
                      className={`activity-badge ${
                        detail.volume_metrics.activity_ratio >= 1.5 ? 'high' : ''
                      }`}
                    >
                      {detail.volume_metrics.activity_ratio}x activity ratio
                    </span>
                  ) : null}
                </div>
                <div className="volume-grid">
                  <div className="volume-item">
                    <span>Current</span>
                    <strong>{formatCompactVolume(detail.volume_metrics?.current_volume)}</strong>
                  </div>
                  <div className="volume-item">
                    <span>5-day avg</span>
                    <strong>{formatCompactVolume(detail.volume_metrics?.avg_5d)}</strong>
                  </div>
                  <div className="volume-item">
                    <span>20-day avg</span>
                    <strong>{formatCompactVolume(detail.volume_metrics?.avg_20d)}</strong>
                  </div>
                  <div className="volume-item">
                    <span>60-day avg</span>
                    <strong>{formatCompactVolume(detail.volume_metrics?.avg_60d)}</strong>
                  </div>
                </div>
                {detail.volume_metrics?.status_note ? (
                  <p className="volume-note">{detail.volume_metrics.status_note}</p>
                ) : null}
              </div>
            </div>

            {/* Section 3: Sector Performance */}
            <div className="drawer-section drawer-animate-item">
              <h3 className="drawer-section-title">Sector Performance</h3>
              {detail.sector_performance ? (
                <div className="volume-activity-box">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <strong>{detail.sector_performance.sector} Sector</strong>
                      <p className="subtle" style={{ margin: '2px 0 0', fontSize: '0.8rem' }}>
                        Sector avg move:{' '}
                        <strong className={toneForValue(detail.sector_performance.sector_change_percent)}>
                          {formatPercent(detail.sector_performance.sector_change_percent)}
                        </strong>
                      </p>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span className="ticker-sublabel">Stock move</span>
                      <strong className={toneForValue(detail.sector_performance.stock_change_percent)}>
                        {formatPercent(detail.sector_performance.stock_change_percent)}
                      </strong>
                    </div>
                  </div>

                  {detail.sector_performance.takeaway ? (
                    <div className="why-card" style={{ marginTop: '8px' }}>
                      <strong>Takeaway:</strong>
                      <p style={{ margin: '4px 0 0', fontSize: '0.86rem' }}>
                        {detail.sector_performance.takeaway}
                      </p>
                    </div>
                  ) : null}

                  {detail.sector_performance.peers?.length ? (
                    <div style={{ marginTop: '10px' }}>
                      <span className="ticker-sublabel" style={{ marginBottom: '8px', display: 'block' }}>
                        Sector Peers ({detail.sector_performance.sector}):
                      </span>
                      <div
                        className="volume-grid"
                        style={{
                          gridTemplateColumns: `repeat(${Math.min(detail.sector_performance.peers.length, 4)}, minmax(0, 1fr))`,
                        }}
                      >
                        {detail.sector_performance.peers.map((peer) => (
                          <div className="volume-item" key={peer.symbol}>
                            <span>{peer.display_name}</span>
                            <strong className={toneForValue(peer.day_change_percent)}>
                              {formatPercent(peer.day_change_percent)}
                            </strong>
                            <span className="ticker-sublabel">{peer.symbol}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : (
                <p className="subtle">No sector performance metrics available.</p>
              )}
            </div>

            {/* Section 4: Similar Companies (Peers) */}
            <div className="drawer-section drawer-animate-item">
              <h3 className="drawer-section-title">Similar Companies</h3>
              {detail.peers?.length ? (
                <table className="peer-table">
                  <thead>
                    <tr>
                      <th>Company</th>
                      <th>Symbol</th>
                      <th>Today&apos;s Move</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.peers.map((peer) => (
                      <tr key={peer.symbol}>
                        <td>
                          <strong>{peer.display_name}</strong>
                        </td>
                        <td>
                          <span className="ticker-sublabel">{peer.symbol}</span>
                        </td>
                        <td>
                          <span className={toneForValue(peer.day_change_percent)}>
                            {formatPercent(peer.day_change_percent)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="subtle">No peer mapping available for this sector.</p>
              )}
            </div>

            {/* Section 4: News & Events */}
            <div className="drawer-section drawer-animate-item">
              <h3 className="drawer-section-title">News &amp; Events</h3>
              {detail.news?.length ? (
                <div className="news-list">
                  {detail.news.map((item, idx) => (
                    <a
                      key={idx}
                      href={item.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="news-card"
                    >
                      <h4 className="news-card-title">{item.title}</h4>
                      <div className="news-card-meta">
                        <span>{item.publisher}</span>
                        {item.pub_date ? <span>· {formatTimeAgo(item.pub_date)}</span> : null}
                      </div>
                    </a>
                  ))}
                </div>
              ) : (
                <div className="empty-state">
                  <p>No recent news articles found for this symbol.</p>
                </div>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}

function Metric({ label, value, tone = '' }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
    </div>
  )
}

function MiniLineChart({ series }) {
  const width = 360
  const height = 160
  const values = series.map((point) => point.close).filter((value) => typeof value === 'number')
  if (!values.length) {
    return <p className="subtle">No price history available.</p>
  }
  if (series.length === 1) {
    const y = height / 2
    return (
      <div className="chart-wrap">
        <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="Away period stock price line chart">
          <line x1="0" y1={y} x2={width} y2={y} stroke="var(--positive)" strokeWidth="3" strokeDasharray="6 4" />
        </svg>
        <div className="chart-axis">
          <span>Checkpoint {series[0]?.date}</span>
          <span>Latest {series[0]?.date}</span>
        </div>
      </div>
    )
  }
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const path = series
    .map((point, index) => {
      const x = (index / Math.max(series.length - 1, 1)) * width
      const y = height - (((point.close || min) - min) / range) * height
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`
    })
    .join(' ')
  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="Away period stock price line chart">
        <path d={path} fill="none" stroke="var(--positive)" strokeWidth="3" strokeLinecap="round" />
      </svg>
      <div className="chart-axis">
        <span>{series[0]?.date}</span>
        <span>{series.at(-1)?.date}</span>
      </div>
    </div>
  )
}

function TinySparkline({ points }) {
  const values = points.map((point) => point.close).filter((value) => typeof value === 'number')
  if (!values.length) return null
  const width = 220
  const height = 64
  if (values.length === 1) {
    return (
      <svg viewBox={`0 0 ${width} ${height}`} className="sparkline" role="img" aria-label="Recent trend sparkline">
        <line x1="0" y1={height / 2} x2={width} y2={height / 2} stroke="var(--accent)" strokeWidth="2.5" strokeDasharray="4 4" />
      </svg>
    )
  }
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const path = points
    .map((point, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * width
      const y = height - (((point.close || min) - min) / range) * height
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`
    })
    .join(' ')
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="sparkline" role="img" aria-label="Recent trend sparkline">
      <path d={path} fill="none" stroke="var(--accent)" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  )
}

function EmptyState({ title, body }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
  )
}

function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function formatCurrency(value) {
  if (typeof value !== 'number') return 'No price'
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(value)
}

function formatPercent(value) {
  if (typeof value !== 'number') return 'No data'
  const prefix = value > 0 ? '+' : ''
  return `${prefix}${(value * 100).toFixed(2)}%`
}

function formatDate(value) {
  if (!value) return 'Unknown date'
  return new Date(value).toLocaleDateString('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: 'numeric',
    month: 'short',
  })
}

function formatTimeAgo(value) {
  if (!value) return ''
  const d = new Date(value)
  if (isNaN(d.getTime())) return ''
  const sec = Math.max(0, Math.floor((new Date() - d) / 1000))
  if (sec < 3600) return `${Math.max(1, Math.floor(sec / 60))}m ago`
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`
  return `${Math.floor(sec / 86400)}d ago`
}

function formatCompactVolume(value) {
  if (typeof value !== 'number' || isNaN(value)) return 'N/A'
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)}B`
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return value.toString()
}

function toneForValue(value) {
  if (typeof value !== 'number') return ''
  if (value > 0) return 'positive'
  if (value < 0) return 'negative'
  return 'neutral'
}

function formatNumber(value) {
  if (typeof value !== 'number') return 'No data'
  return value.toFixed(2)
}

function formatDateTime(value) {
  if (!value) return 'N/A'
  const date = new Date(value)
  if (isNaN(date.getTime())) return String(value)
  return date.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

function formatElapsed(value) {
  if (!value) return 'just now'
  const date = new Date(value)
  const seconds = Math.max(0, Math.floor((new Date() - date) / 1000))
  if (seconds < 3600) {
    const mins = Math.max(1, Math.floor(seconds / 60))
    return mins === 1 ? '1 minute ago' : `${mins} minutes ago`
  } else if (seconds < 86400) {
    const hours = Math.floor(seconds / 3600)
    return hours === 1 ? '1 hour ago' : `${hours} hours ago`
  } else {
    const days = Math.floor(seconds / 86400)
    return days === 1 ? '1 day ago' : `${days} days ago`
  }
}

export default App


