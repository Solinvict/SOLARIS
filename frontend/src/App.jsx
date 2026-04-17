/* SPDX-License-Identifier: MPL-2.0 */

import { useEffect, useState } from 'react'
import { SolarisScene } from './components/SolarisScene'
import { useSolarisStore } from './store/useSolarisStore'

function ScopeField({ label, field, value, onChange }) {
  return (
    <label className="scope-field">
      <span>{label}</span>
      <input value={value || ''} onChange={(event) => onChange(field, event.target.value)} />
    </label>
  )
}

function LayerToggle({ label, checked, onChange }) {
  return (
    <label className="toggle-row">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  )
}

function PanelHeader({ title, onClose }) {
  return (
    <div className="panel-header">
      <div className="section-title">{title}</div>
      <button className="close-button" onClick={onClose}>
        close
      </button>
    </div>
  )
}

export default function App() {
  const [draftQuery, setDraftQuery] = useState('')
  const [leftOpen, setLeftOpen] = useState(false)
  const [rightOpen, setRightOpen] = useState(false)
  const [bottomOpen, setBottomOpen] = useState(false)
  const bootstrap = useSolarisStore((state) => state.bootstrap)
  const scope = useSolarisStore((state) => state.scope)
  const scene = useSolarisStore((state) => state.scene)
  const layers = useSolarisStore((state) => state.layers)
  const showDivergence = useSolarisStore((state) => state.showDivergence)
  const connection = useSolarisStore((state) => state.connection)
  const inspector = useSolarisStore((state) => state.inspector)
  const topPatterns = useSolarisStore((state) => state.topPatterns)
  const topRecall = useSolarisStore((state) => state.topRecall)
  const selectedNodeId = useSolarisStore((state) => state.selectedNodeId)
  const loading = useSolarisStore((state) => state.loading)
  const error = useSolarisStore((state) => state.error)
  const bootstrapApp = useSolarisStore((state) => state.bootstrapApp)
  const setScopeField = useSolarisStore((state) => state.setScopeField)
  const loadLanding = useSolarisStore((state) => state.loadLanding)
  const runRecall = useSolarisStore((state) => state.runRecall)
  const inspectArtifact = useSolarisStore((state) => state.inspectArtifact)
  const setLayer = useSolarisStore((state) => state.setLayer)
  const toggleDivergence = useSolarisStore((state) => state.toggleDivergence)

  useEffect(() => {
    bootstrapApp()
  }, [bootstrapApp])

  const openInspector = (artifactType, artifactId, nodeId = '') => {
    setRightOpen(true)
    setBottomOpen(true)
    inspectArtifact(artifactType, artifactId, nodeId)
  }

  return (
    <div className="app-shell">
      <div className="app-backdrop" aria-hidden />

      <main className="scene-shell">
        {scene ? (
          <SolarisScene
            scene={scene}
            layers={layers}
            showDivergence={showDivergence}
            selectedNodeId={selectedNodeId}
            onSelect={(node) => openInspector(node.artifact_type, node.artifact_id, node.id)}
          />
        ) : (
          <div className="loading-state">Loading Solaris scene...</div>
        )}
        {loading ? <div className="scene-badge">Refreshing memory field...</div> : null}
        {error ? <div className="scene-error">{error}</div> : null}
      </main>

      <div className="top-left-cluster">
        <div className="brand-mark panel">
          <div className="eyebrow">Standalone Memory Observatory</div>
          <h1>Solaris</h1>
        </div>

        <div className="control-dock panel">
          <button className="pill action-pill" onClick={() => setLeftOpen((open) => !open)}>
            {leftOpen ? 'hide controls' : 'controls'}
          </button>
          <button className="pill action-pill" onClick={() => setRightOpen((open) => !open)}>
            {rightOpen ? 'hide inspector' : 'inspector'}
          </button>
          <button className="pill action-pill" onClick={() => setBottomOpen((open) => !open)}>
            {bottomOpen ? 'hide timeline' : 'timeline'}
          </button>
        </div>
      </div>

      <div className="status-dock panel">
        <div className={`pill ${connection.status}`}>{connection.status}</div>
        <div className="pill">read-only v1</div>
        <div className="pill">db {connection.dbSignature || 'pending'}</div>
      </div>

      {leftOpen ? (
        <aside className="floating-drawer left panel">
          <div className="drawer-content">
            <PanelHeader title="Controls" onClose={() => setLeftOpen(false)} />

            <section>
              <div className="section-title">Scope</div>
              <ScopeField label="Tenant" field="tenant" value={scope?.tenant} onChange={setScopeField} />
              <ScopeField label="Namespace" field="namespace" value={scope?.namespace} onChange={setScopeField} />
              <ScopeField label="Workspace" field="workspace" value={scope?.workspace} onChange={setScopeField} />
              <ScopeField label="Project" field="project" value={scope?.project} onChange={setScopeField} />
              <button className="action-button" onClick={() => loadLanding()}>
                Refresh Scope
              </button>
            </section>

            <section>
              <div className="section-title">Recall</div>
              <form
                onSubmit={(event) => {
                  event.preventDefault()
                  setRightOpen(true)
                  runRecall(draftQuery)
                }}
              >
                <textarea
                  className="query-input"
                  value={draftQuery}
                  onChange={(event) => setDraftQuery(event.target.value)}
                  placeholder="Ask Solaris what to surface, explain, or connect..."
                />
                <button className="action-button primary" type="submit">
                  Run Recall
                </button>
              </form>
            </section>

            <section>
              <div className="section-title">Layers</div>
              {bootstrap?.layers?.map((layer) => (
                <LayerToggle
                  key={layer.key}
                  label={layer.label}
                  checked={layers[layer.key]}
                  onChange={(value) => setLayer(layer.key, value)}
                />
              ))}
              <LayerToggle label="Divergence" checked={showDivergence} onChange={() => toggleDivergence()} />
            </section>
          </div>
        </aside>
      ) : null}

      {rightOpen ? (
        <aside className="floating-drawer right panel">
          <div className="drawer-content">
            <PanelHeader title="Inspector" onClose={() => setRightOpen(false)} />

            <section>
              {inspector ? (
                <>
                  <h2>{inspector.scene_focus?.inspector_cards?.[0]?.title || inspector.artifact_type}</h2>
                  <p className="muted-copy">
                    {inspector.explain?.artifact_type} - {inspector.artifact_id}
                  </p>
                  <div className="inspector-block">
                    <strong>Editorial state</strong>
                    <code>{JSON.stringify(inspector.explain?.editorial_state || {}, null, 2)}</code>
                  </div>
                  <div className="inspector-block">
                    <strong>Decision history</strong>
                    <code>{JSON.stringify(inspector.explain?.decisions || [], null, 2)}</code>
                  </div>
                  <div className="inspector-block">
                    <strong>Graph neighborhood</strong>
                    <code>{JSON.stringify(inspector.graph || {}, null, 2)}</code>
                  </div>
                </>
              ) : (
                <p className="muted-copy">
                  Select a recall node, memory artifact, or graph node to descend into provenance and neighborhood context.
                </p>
              )}
            </section>

            <section>
              <div className="section-title">Top Recall</div>
              <div className="stack-cards">
                {(topRecall || []).map((card) => (
                  <button
                    key={`${card.artifact_type}:${card.artifact_id}`}
                    className="stack-card"
                    onClick={() => openInspector(card.artifact_type, card.artifact_id)}
                  >
                    <strong>{card.title}</strong>
                    <span>{card.summary}</span>
                  </button>
                ))}
              </div>
            </section>

            <section>
              <div className="section-title">Fractal Projection</div>
              <div className="stack-cards compact">
                {(topPatterns || []).map((pattern) => (
                  <div key={pattern.pattern_id || pattern.label} className="stack-card static">
                    <strong>{pattern.label}</strong>
                    <span>{pattern.summary}</span>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </aside>
      ) : null}

      {bottomOpen ? (
        <footer className="bottom-sheet panel">
          <div className="drawer-content">
            <PanelHeader title="Timeline" onClose={() => setBottomOpen(false)} />
            <div className="timeline-header">
              <div>
                <div className="section-title">Timeline</div>
                <h2>Archive drift and active provenance</h2>
              </div>
              <div className="timeline-meta">
                <span>{scene?.archive_density?.recorded_events || 0} recorded events</span>
                <span>{scene?.graph_summary?.relation_count || 0} relation edges</span>
                <span>{scene?.divergence_summary?.count || 0} divergences</span>
              </div>
            </div>
            <div className="timeline-list">
              {(inspector?.artifact_timeline || []).slice(0, 10).map((item) => (
                <div className="timeline-item" key={item.event_id || `${item.timestamp}:${item.label}`}>
                  <strong>{item.label || item.kind || item.raw_text || item.timestamp}</strong>
                  <span>{item.timestamp || item.start_at || ''}</span>
                </div>
              ))}
              {!inspector?.artifact_timeline?.length ? (
                <div className="timeline-item empty">
                  <strong>No focused artifact timeline yet.</strong>
                  <span>Inspect a node to see its supporting events and temporal drift.</span>
                </div>
              ) : null}
            </div>
          </div>
        </footer>
      ) : null}
    </div>
  )
}
