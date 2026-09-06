import { useEffect, useRef } from 'react'
import { Renderer, Program, Mesh, Triangle } from 'ogl'

const VERTEX_SHADER = /* glsl */ `
  attribute vec2 uv;
  attribute vec2 position;
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = vec4(position, 0.0, 1.0);
  }
`

const FRAGMENT_SHADER = /* glsl */ `
  precision highp float;
  uniform float uTime;
  uniform vec3 uColor1;
  uniform vec3 uColor2;
  uniform vec3 uColor3;
  uniform vec3 uColor4;
  uniform vec2 uResolution;
  uniform vec2 uMouse;
  uniform float uSpeed;
  uniform float uAmplitude;
  varying vec2 vUv;

  float wave(vec2 st, float time) {
    float d = 0.0;
    d += sin(st.x * 2.8 + time * uSpeed * 0.85) * 0.5;
    d += cos(st.y * 3.2 - time * uSpeed * 1.1) * 0.5;
    d += sin((st.x + st.y) * 2.1 + time * uSpeed * 0.7) * 0.4;
    d += cos((st.x * 0.9 - st.y * 1.4) + time * uSpeed * 0.5) * 0.3;
    return d * uAmplitude;
  }

  void main() {
    vec2 st = gl_FragCoord.xy / uResolution.xy;

    vec2 mouseOffset = (uMouse - vec2(0.5)) * 0.15;
    st += mouseOffset;

    float w1 = wave(st, uTime);
    float w2 = wave(st * 1.25 + vec2(0.4, 0.8), uTime * 0.75 + 1.5);
    float w3 = wave(st * 0.85 - vec2(0.6, 0.3), uTime * 0.6 + 2.8);

    float mixFactor1 = clamp(st.y + w1 * 0.4, 0.0, 1.0);
    float mixFactor2 = clamp(st.x + w2 * 0.4, 0.0, 1.0);
    float mixFactor3 = clamp((st.x + st.y) * 0.5 + w3 * 0.3, 0.0, 1.0);

    vec3 colA = mix(uColor1, uColor2, mixFactor1);
    vec3 colB = mix(uColor3, uColor4, mixFactor2);

    float pulse = 0.5 + 0.5 * sin(uTime * 0.35 + w1 * 0.8);
    vec3 finalColor = mix(colA, colB, pulse);
    finalColor = mix(finalColor, uColor1, mixFactor3 * 0.15);

    gl_FragColor = vec4(finalColor, 1.0);
  }
`

function hexToRgb(hex) {
  let c = hex.replace('#', '')
  if (c.length === 3) c = c.split('').map((x) => x + x).join('')
  const num = parseInt(c, 16)
  return [(num >> 16 & 255) / 255, (num >> 8 & 255) / 255, (num & 255) / 255]
}

export default function GradientWaves({
  color1 = '#F5F0EB',
  color2 = '#E8DFC9',
  color3 = '#C9D6C9',
  color4 = '#D6C8C7',
  speed = 0.5,
  amplitude = 0.65,
  interactive = true,
}) {
  const containerRef = useRef(null)
  const mouseRef = useRef([0.5, 0.5])
  const targetMouseRef = useRef([0.5, 0.5])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const effectiveSpeed = prefersReducedMotion ? 0.05 : speed

    let renderer
    try {
      renderer = new Renderer({
        dpr: Math.min(window.devicePixelRatio, 2),
        alpha: true,
        webgl: 2,
      })
    } catch {
      try {
        renderer = new Renderer({
          dpr: Math.min(window.devicePixelRatio, 2),
          alpha: true,
          webgl: 1,
        })
      } catch {
        return
      }
    }

    const gl = renderer.gl
    const canvas = gl.canvas
    canvas.style.width = '100%'
    canvas.style.height = '100%'
    canvas.style.display = 'block'
    container.appendChild(canvas)

    const geometry = new Triangle(gl)

    const program = new Program(gl, {
      vertex: VERTEX_SHADER,
      fragment: FRAGMENT_SHADER,
      uniforms: {
        uTime: { value: 0 },
        uColor1: { value: hexToRgb(color1) },
        uColor2: { value: hexToRgb(color2) },
        uColor3: { value: hexToRgb(color3) },
        uColor4: { value: hexToRgb(color4) },
        uResolution: { value: [container.clientWidth || 800, container.clientHeight || 600] },
        uMouse: { value: [0.5, 0.5] },
        uSpeed: { value: effectiveSpeed },
        uAmplitude: { value: amplitude },
      },
    })

    const mesh = new Mesh(gl, { geometry, program })

    function resize() {
      if (!container) return
      const width = container.clientWidth || window.innerWidth
      const height = container.clientHeight || window.innerHeight
      renderer.setSize(width, height)
      program.uniforms.uResolution.value = [width, height]
    }

    window.addEventListener('resize', resize)
    resize()

    function handleMouseMove(e) {
      if (!interactive || !container) return
      const rect = container.getBoundingClientRect()
      const x = (e.clientX - rect.left) / rect.width
      const y = 1.0 - (e.clientY - rect.top) / rect.height
      targetMouseRef.current = [x, y]
    }

    if (interactive) {
      window.addEventListener('mousemove', handleMouseMove)
    }

    let animationId
    let startTime = performance.now()

    function update(t) {
      animationId = requestAnimationFrame(update)
      const elapsed = (t - startTime) * 0.001
      program.uniforms.uTime.value = elapsed

      mouseRef.current[0] += (targetMouseRef.current[0] - mouseRef.current[0]) * 0.05
      mouseRef.current[1] += (targetMouseRef.current[1] - mouseRef.current[1]) * 0.05
      program.uniforms.uMouse.value = mouseRef.current

      renderer.render({ scene: mesh })
    }

    animationId = requestAnimationFrame(update)

    return () => {
      cancelAnimationFrame(animationId)
      window.removeEventListener('resize', resize)
      if (interactive) {
        window.removeEventListener('mousemove', handleMouseMove)
      }
      if (container && canvas.parentNode === container) {
        container.removeChild(canvas)
      }
      try {
        gl.getExtension('WEBGL_lose_context')?.loseContext()
      } catch {
        // Context clean up
      }
    }
  }, [color1, color2, color3, color4, speed, amplitude, interactive])

  return (
    <div
      ref={containerRef}
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        pointerEvents: 'none',
      }}
    />
  )
}
