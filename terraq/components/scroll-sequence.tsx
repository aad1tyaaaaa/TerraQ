'use client'

import { useEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(ScrollTrigger)

const FRAME_COUNT = 200

function frameSrc(i: number) {
  return `/landing-page/ezgif-frame-${String(i + 1).padStart(3, '0')}.jpg`
}

export function ScrollSequence() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const [loaded, setLoaded] = useState(false)
  const [progress, setProgress] = useState(0)
  const imagesRef = useRef<HTMLImageElement[]>([])
  const frameIndexRef = useRef(0)

  // Preload all frames
  useEffect(() => {
    let loadedCount = 0
    const images: HTMLImageElement[] = new Array(FRAME_COUNT)

    for (let i = 0; i < FRAME_COUNT; i++) {
      const img = new Image()
      img.src = frameSrc(i)
      img.onload = () => {
        loadedCount++
        setProgress(loadedCount / FRAME_COUNT)
        if (loadedCount === FRAME_COUNT) {
          imagesRef.current = images
          setLoaded(true)
        }
      }
      img.onerror = img.onload
      images[i] = img
    }
  }, [])

  // Set up canvas rendering + ScrollTrigger
  useEffect(() => {
    if (!loaded) return
    const canvas = canvasRef.current!
    const ctx = canvas.getContext('2d')!
    const wrapper = wrapperRef.current!

    function resize() {
      const dpr = window.devicePixelRatio || 1
      canvas.width = window.innerWidth * dpr
      canvas.height = window.innerHeight * dpr
      canvas.style.width = `${window.innerWidth}px`
      canvas.style.height = `${window.innerHeight}px`
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      drawFrame(frameIndexRef.current)
    }

    function drawFrame(index: number) {
      const img = imagesRef.current[index]
      if (!img) return
      const cw = window.innerWidth
      const ch = window.innerHeight
      const ir = img.naturalWidth / img.naturalHeight
      const cr = cw / ch
      let dw: number, dh: number, dx: number, dy: number
      if (cr > ir) {
        dw = cw
        dh = cw / ir
        dx = 0
        dy = (ch - dh) / 2
      } else {
        dh = ch
        dw = ch * ir
        dy = 0
        dx = (cw - dw) / 2
      }
      ctx.clearRect(0, 0, cw, ch)
      ctx.drawImage(img, dx, dy, dw, dh)
    }

    resize()
    window.addEventListener('resize', resize)

    // Draw first frame
    drawFrame(0)

    // ScrollTrigger: pin the wrapper and scrub through frames
    const st = ScrollTrigger.create({
      trigger: wrapper,
      start: 'top top',
      end: `+=${window.innerHeight * 5}`,
      pin: true,
      scrub: 0.5,
      onUpdate: (self) => {
        const index = Math.min(FRAME_COUNT - 1, Math.floor(self.progress * FRAME_COUNT))
        if (index !== frameIndexRef.current) {
          frameIndexRef.current = index
          drawFrame(index)
        }
        // Fade in at start, stay fully visible at end
        const opacity = self.progress < 0.05 ? self.progress / 0.05 : 1
        canvas.style.opacity = String(opacity)
      },
    })

    return () => {
      window.removeEventListener('resize', resize)
      st.kill()
    }
  }, [loaded])

  return (
    <div ref={wrapperRef} className="relative w-full h-screen">
      {!loaded && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 z-20 bg-black">
          <div className="w-48 h-1 rounded-full bg-white/10 overflow-hidden">
            <div
              className="h-full bg-cyan-400 rounded-full transition-all duration-200"
              style={{ width: `${progress * 100}%` }}
            />
          </div>
          <span className="text-xs text-white/40">Loading frames… {Math.round(progress * 100)}%</span>
        </div>
      )}
      {/* First frame as static bg until canvas is ready */}
      <div
        className="absolute inset-0 bg-cover bg-center"
        style={{ backgroundImage: `url(${frameSrc(0)})` }}
      />
      <canvas
        ref={canvasRef}
        className="relative z-10 w-full h-full block"
        style={{ opacity: loaded ? 1 : 0 }}
      />
    </div>
  )
}
