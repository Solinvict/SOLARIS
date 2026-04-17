/* SPDX-License-Identifier: MPL-2.0 */

const API_BASE = import.meta.env.VITE_SOLARIS_API_BASE || ''

function deriveWebSocketUrl() {
  if (import.meta.env.VITE_SOLARIS_WS_URL) {
    return import.meta.env.VITE_SOLARIS_WS_URL
  }

  if (API_BASE) {
    const apiUrl = new URL(API_BASE, window.location.origin)
    apiUrl.protocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:'
    apiUrl.pathname = '/ws'
    apiUrl.search = ''
    apiUrl.hash = ''
    return apiUrl.toString()
  }

  if (import.meta.env.DEV) {
    return 'ws://127.0.0.1:8766/ws'
  }

  return `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`
}

const WS_URL = deriveWebSocketUrl()

function toUrl(path) {
  return `${API_BASE}${path}`
}

async function handleResponse(response) {
  if (!response.ok) {
    const payload = await response.text()
    throw new Error(payload || `Request failed with status ${response.status}`)
  }
  return response.json()
}

export async function getJson(path) {
  const response = await fetch(toUrl(path), {
    headers: {
      Accept: 'application/json',
    },
  })
  return handleResponse(response)
}

export async function postJson(path, body) {
  const response = await fetch(toUrl(path), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(body),
  })
  return handleResponse(response)
}

export function openSocket(scope) {
  const params = new URLSearchParams(scope || {})
  return new WebSocket(`${WS_URL}?${params.toString()}`)
}
