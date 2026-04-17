/* SPDX-License-Identifier: MPL-2.0 */

import { create } from 'zustand'
import { getJson, openSocket, postJson } from '../api/client'

const DEFAULT_LAYERS = {
  archive: true,
  editorial_memory: true,
  graph_structure: true,
  active_recall: true,
  fractal_projection: true,
}

function queryString(scope) {
  const params = new URLSearchParams(scope || {})
  return params.toString()
}

function artifactUrl(scope, artifactType, artifactId) {
  return `/api/artifacts/${artifactType}/${artifactId}?${queryString(scope)}`
}

export const useSolarisStore = create((set, get) => ({
  bootstrap: null,
  scope: null,
  scene: null,
  topPatterns: [],
  topRecall: [],
  lastQuery: '',
  activeView: 'landing',
  inspector: null,
  selectedNodeId: '',
  layers: DEFAULT_LAYERS,
  showDivergence: true,
  connection: { status: 'idle', lastEvent: '', dbSignature: '' },
  loading: false,
  error: '',
  socket: null,

  setScopeField(field, value) {
    const scope = { ...(get().scope || {}), [field]: value }
    set({ scope })
  },

  setLayer(key, value) {
    set((state) => ({ layers: { ...state.layers, [key]: value } }))
  },

  toggleDivergence() {
    set((state) => ({ showDivergence: !state.showDivergence }))
  },

  async bootstrapApp() {
    set({ loading: true, error: '' })
    try {
      const bootstrap = await getJson('/api/bootstrap')
      set({
        bootstrap,
        scope: bootstrap.default_scope,
        loading: false,
      })
      await get().loadLanding(bootstrap.default_scope)
      get().connectSocket()
    } catch (error) {
      set({ loading: false, error: String(error.message || error) })
    }
  },

  async loadLanding(scopeOverride) {
    const scope = scopeOverride || get().scope
    if (!scope) return
    set({ loading: true, error: '', activeView: 'landing', inspector: null, selectedNodeId: '' })
    try {
      const payload = await getJson(`/api/landing?${queryString(scope)}`)
      set({
        scope,
        scene: payload.scene,
        topPatterns: payload.top_patterns || [],
        topRecall: payload.top_recall || [],
        loading: false,
        lastQuery: '',
      })
      const socket = get().socket
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'scope_state', payload: scope }))
      }
    } catch (error) {
      set({ loading: false, error: String(error.message || error) })
    }
  },

  async runRecall(query) {
    const scope = get().scope
    if (!scope) return
    set({ loading: true, error: '', activeView: 'recall', lastQuery: query })
    try {
      const payload = await postJson('/api/recall', {
        query,
        scope,
        scope_mode: 'local',
        recall_mode: 'default',
        include_explanations: true,
      })
      set({
        scene: payload.scene,
        topPatterns: payload.top_patterns || [],
        loading: false,
        inspector: null,
        selectedNodeId: '',
      })
      const socket = get().socket
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'scope_state', payload: scope }))
      }
    } catch (error) {
      set({ loading: false, error: String(error.message || error) })
    }
  },

  async inspectArtifact(artifactType, artifactId, nodeId = '') {
    if (!artifactType || !artifactId || artifactType === 'pattern') {
      set({ selectedNodeId: nodeId })
      return
    }
    try {
      const payload = await getJson(artifactUrl(get().scope, artifactType, artifactId))
      set({
        inspector: payload,
        selectedNodeId: nodeId,
      })
    } catch (error) {
      set({ error: String(error.message || error) })
    }
  },

  async refetchActiveView() {
    if (get().activeView === 'recall' && get().lastQuery) {
      await get().runRecall(get().lastQuery)
      return
    }
    await get().loadLanding()
  },

  connectSocket() {
    const currentSocket = get().socket
    if (currentSocket) {
      currentSocket.close()
    }
    const scope = get().scope
    if (!scope) return
    const socket = openSocket(scope)
    socket.onopen = () => {
      set({ connection: { ...get().connection, status: 'connected' } })
    }
    socket.onmessage = async (event) => {
      try {
        const payload = JSON.parse(event.data)
        const type = String(payload.type || '')
        const inner = payload.payload || {}
        if (type === 'hello') {
          set({
            connection: {
              status: 'connected',
              lastEvent: 'hello',
              dbSignature: inner.db_signature || '',
            },
          })
        } else if (type === 'scope_state') {
          set({
            scope: inner,
            connection: { ...get().connection, lastEvent: 'scope_state' },
          })
        } else if (type === 'activity') {
          set({
            connection: {
              status: 'connected',
              lastEvent: 'activity',
              dbSignature: inner.db_signature || get().connection.dbSignature,
            },
          })
        } else if (type === 'invalidate') {
          set({
            connection: {
              status: 'connected',
              lastEvent: 'invalidate',
              dbSignature: inner.db_signature || get().connection.dbSignature,
            },
          })
          await get().refetchActiveView()
        }
      } catch (_error) {
        set({ connection: { ...get().connection, lastEvent: 'malformed' } })
      }
    }
    socket.onclose = () => {
      set({ connection: { ...get().connection, status: 'disconnected' }, socket: null })
      window.setTimeout(() => {
        if (!get().socket) get().connectSocket()
      }, 2500)
    }
    socket.onerror = () => {
      set({ connection: { ...get().connection, status: 'faulted' } })
    }
    set({ socket })
  },
}))
