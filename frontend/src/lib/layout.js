/* SPDX-License-Identifier: MPL-2.0 */

const LAYER_RADIUS = {
  archive: 1.1,
  editorial_memory: 2.15,
  graph_structure: 3.05,
  active_recall: 4.05,
  fractal_projection: 5.2,
}

function hashString(value) {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash += (hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24)
  }
  return Math.abs(hash >>> 0)
}

function normalized(value) {
  return (value % 1000) / 1000
}

function layerRadius(layer) {
  return LAYER_RADIUS[layer] || 2.4
}

function timestampHeight(timestamp) {
  if (!timestamp) return 0
  const millis = Date.parse(timestamp)
  if (Number.isNaN(millis)) return 0
  const day = 1000 * 60 * 60 * 24
  return ((millis / day) % 21) / 4 - 2.5
}

export function computeNodeLayout(nodes) {
  const positions = {}
  nodes.forEach((node, index) => {
    const basis = hashString(`${node.id}:${node.label}:${index}`)
    const theta = normalized(basis) * Math.PI * 2
    const phi = normalized(Math.floor(basis / 7)) * Math.PI
    const radius = layerRadius(node.layer) + normalized(Math.floor(basis / 17)) * 0.35
    const timeLift = timestampHeight(node.timestamp)
    const x = Math.cos(theta) * radius
    const z = Math.sin(theta) * radius
    const y = Math.cos(phi) * 0.85 + timeLift
    positions[node.id] = [x, y, z]
  })
  return positions
}
