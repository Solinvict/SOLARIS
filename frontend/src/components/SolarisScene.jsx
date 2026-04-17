/* SPDX-License-Identifier: MPL-2.0 */

import { Canvas } from '@react-three/fiber'
import { EffectComposer, Bloom } from '@react-three/postprocessing'
import { Line, OrbitControls, Stars } from '@react-three/drei'
import { computeNodeLayout } from '../lib/layout'

const LAYER_COLOR = {
  archive: '#74d7ff',
  editorial_memory: '#ffbf69',
  graph_structure: '#6effe6',
  active_recall: '#f6f1d5',
  fractal_projection: '#ff9d5c',
}

function TemporalStrata({ nodes }) {
  const archiveNodes = nodes.filter((node) => node.layer === 'archive')
  const count = Math.min(5, Math.max(2, archiveNodes.length ? Math.ceil(archiveNodes.length / 6) : 2))
  const rings = []
  for (let index = 0; index < count; index += 1) {
    const radius = 0.95 + index * 0.45
    const points = []
    for (let step = 0; step <= 48; step += 1) {
      const theta = (step / 48) * Math.PI * 2
      points.push([Math.cos(theta) * radius, -2.5 + index * 1.1, Math.sin(theta) * radius])
    }
    rings.push(
      <Line
        key={`strata-${index}`}
        points={points}
        color="#74d7ff"
        lineWidth={0.7}
        transparent
        opacity={0.18}
      />
    )
  }
  return <group>{rings}</group>
}

function ArchiveField({ nodes, positions }) {
  const archiveNodes = nodes.filter((node) => node.layer === 'archive' && !node.divergence)
  const coords = []
  archiveNodes.forEach((node) => {
    const point = positions[node.id]
    if (point) coords.push(...point)
  })
  if (!coords.length) return null
  return (
    <points>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={coords.length / 3}
          array={new Float32Array(coords)}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial color={LAYER_COLOR.archive} size={0.05} sizeAttenuation transparent opacity={0.55} />
    </points>
  )
}

function LayerMesh({ node, position, selected, onSelect }) {
  const color = node.divergence ? '#ff8f8f' : LAYER_COLOR[node.layer] || '#ffffff'
  const commonProps = {
    position,
    onClick: (event) => {
      event.stopPropagation()
      onSelect(node)
    },
  }

  if (node.layer === 'fractal_projection') {
    return (
      <mesh {...commonProps}>
        <torusGeometry args={[0.17 + node.emphasis * 0.14, 0.035, 12, 48]} />
        <meshStandardMaterial color={color} transparent opacity={0.26} emissive={color} emissiveIntensity={1.15} />
      </mesh>
    )
  }

  if (node.layer === 'graph_structure') {
    return (
      <mesh {...commonProps}>
        <octahedronGeometry args={[0.11 + node.emphasis * 0.08, 0]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={selected ? 0.95 : 0.42} />
      </mesh>
    )
  }

  if (node.layer === 'active_recall') {
    return (
      <group {...commonProps}>
        <mesh>
          <sphereGeometry args={[0.15 + node.emphasis * 0.08, 24, 24]} />
          <meshStandardMaterial color={color} emissive={color} emissiveIntensity={selected ? 1.65 : 1.15} />
        </mesh>
        <mesh>
          <torusGeometry args={[0.28, 0.012, 12, 64]} />
          <meshBasicMaterial color={color} transparent opacity={0.7} />
        </mesh>
      </group>
    )
  }

  if (node.layer === 'editorial_memory') {
    return (
      <mesh {...commonProps}>
        <sphereGeometry args={[0.1 + node.emphasis * 0.06, 22, 22]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={selected ? 0.9 : 0.3} />
      </mesh>
    )
  }

  return null
}

function SceneEdges({ edges, positions, layers, showDivergence }) {
  return (
    <group>
      {edges.map((edge) => {
        const source = positions[edge.source]
        const target = positions[edge.target]
        if (!source || !target) return null
        if (!layers[edge.layer]) return null
        if (edge.edge_type === 'divergence' && !showDivergence) return null
        const color =
          edge.edge_type === 'divergence'
            ? '#ff8f8f'
            : edge.edge_type === 'recall'
              ? LAYER_COLOR.active_recall
              : edge.edge_type === 'projection'
                ? LAYER_COLOR.fractal_projection
                : LAYER_COLOR.graph_structure
        return (
          <Line
            key={edge.id}
            points={[source, target]}
            color={color}
            lineWidth={edge.edge_type === 'recall' ? 1.4 : 0.9}
            transparent
            opacity={edge.edge_type === 'recall' ? 0.66 : 0.28}
          />
        )
      })}
    </group>
  )
}

export function SolarisScene({ scene, layers, showDivergence, selectedNodeId, onSelect }) {
  const positions = computeNodeLayout(scene?.nodes || [])
  const visibleNodes = (scene?.nodes || []).filter((node) => {
    if (node.divergence && !showDivergence) return false
    return layers[node.layer] ?? true
  })

  return (
    <Canvas camera={{ position: [0, 0.8, 9], fov: 42 }} dpr={[1, 1.5]}>
      <color attach="background" args={['#02060b']} />
      <fog attach="fog" args={['#02060b', 7, 16]} />
      <ambientLight intensity={0.6} />
      <pointLight position={[6, 6, 6]} intensity={1.2} color="#ffd7a6" />
      <pointLight position={[-6, -2, -6]} intensity={0.9} color="#69dfff" />
      <Stars radius={110} depth={70} count={1600} factor={3.4} saturation={0} fade speed={0.15} />
      <TemporalStrata nodes={scene?.nodes || []} />
      <ArchiveField nodes={scene?.nodes || []} positions={positions} />
      <SceneEdges edges={scene?.edges || []} positions={positions} layers={layers} showDivergence={showDivergence} />
      <group rotation={[0.08, 0.22, 0]}>
        {visibleNodes.map((node) => (
          <LayerMesh
            key={node.id}
            node={node}
            position={positions[node.id]}
            selected={selectedNodeId === node.id}
            onSelect={onSelect}
          />
        ))}
      </group>
      <OrbitControls
        makeDefault
        enablePan={false}
        enableDamping
        dampingFactor={0.08}
        minDistance={4.5}
        maxDistance={14}
        rotateSpeed={0.72}
        zoomSpeed={0.9}
      />
      <EffectComposer>
        <Bloom luminanceThreshold={0.18} luminanceSmoothing={0.65} intensity={1.1} mipmapBlur />
      </EffectComposer>
    </Canvas>
  )
}
