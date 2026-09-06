const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000'

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })

  const data = await response.json().catch(() => null)

  if (!response.ok) {
    const message = data?.error || `Request failed with status ${response.status}`
    throw new Error(message)
  }

  return data
}

export const api = {
  bootstrapDemo(payload = {}) {
    return request('/api/demo/bootstrap', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  createUser(payload) {
    return request('/api/users', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  createWatchlist(payload) {
    return request('/api/watchlists', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  getWatchlist(watchlistId) {
    return request(`/api/watchlists/${watchlistId}`)
  },
  getChanges(watchlistId, simulatedPreset = null) {
    const query = simulatedPreset ? `?simulated_checkpoint=${encodeURIComponent(simulatedPreset)}` : ''
    return request(`/api/watchlists/${watchlistId}/changes${query}`)
  },
  getChangeHistory(watchlistId, symbol, simulatedPreset = null) {
    const query = simulatedPreset ? `?simulated_checkpoint=${encodeURIComponent(simulatedPreset)}` : ''
    return request(`/api/watchlists/${watchlistId}/changes/${encodeURIComponent(symbol)}/history${query}`)
  },
  getTimeline(watchlistId, simulatedPreset = null) {
    const query = simulatedPreset ? `?simulated_checkpoint=${encodeURIComponent(simulatedPreset)}` : ''
    return request(`/api/watchlists/${watchlistId}/timeline${query}`)
  },
  addStock(watchlistId, payload) {
    return request(`/api/watchlists/${watchlistId}/stocks`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  deleteStock(watchlistId, symbol) {
    return request(`/api/watchlists/${watchlistId}/stocks/${encodeURIComponent(symbol)}`, {
      method: 'DELETE',
    })
  },
  previewStock(symbol) {
    return request(`/api/stocks/${encodeURIComponent(symbol)}/preview`)
  },
  searchStocks(query = '', sector = '') {
    const params = new URLSearchParams()
    if (query) params.append('q', query)
    if (sector && sector !== 'All') params.append('sector', sector)
    const qs = params.toString() ? `?${params.toString()}` : ''
    return request(`/api/stocks/search${qs}`)
  },
  getStockDetail(symbol, watchlistId = null, simulatedPreset = null) {
    const params = new URLSearchParams()
    if (watchlistId) params.append('watchlist_id', watchlistId)
    if (simulatedPreset) params.append('simulated_checkpoint', simulatedPreset)
    const qs = params.toString() ? `?${params.toString()}` : ''
    return request(`/api/stocks/${encodeURIComponent(symbol)}/detail${qs}`)
  },
  acknowledgeWatchlist(watchlistId) {
    return request(`/api/watchlists/${watchlistId}/acknowledge`, {
      method: 'POST',
      body: JSON.stringify({}),
    })
  },
}


export { API_BASE_URL }
