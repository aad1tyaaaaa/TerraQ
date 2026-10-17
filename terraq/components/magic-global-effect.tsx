'use client';

import { useEffect, useRef } from 'react';
import { gsap } from 'gsap';

const GLOW_COLOR = '255, 255, 255';
const SPOTLIGHT_RADIUS = 300;

export function GlobalMagicEffect() {
  const spotlightRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const spotlight = document.createElement('div');
    spotlight.style.cssText = `
      position: fixed;
      width: 800px;
      height: 800px;
      border-radius: 50%;
      pointer-events: none;
      background: radial-gradient(circle,
        rgba(${GLOW_COLOR}, 0.15) 0%,
        rgba(${GLOW_COLOR}, 0.08) 15%,
        rgba(${GLOW_COLOR}, 0.04) 25%,
        rgba(${GLOW_COLOR}, 0.02) 40%,
        rgba(${GLOW_COLOR}, 0.01) 65%,
        transparent 70%
      );
      z-index: 200;
      opacity: 0;
      transform: translate(-50%, -50%);
      mix-blend-mode: screen;
      will-change: transform, opacity;
    `;
    document.body.appendChild(spotlight);
    spotlightRef.current = spotlight as HTMLDivElement;

    const proximity = SPOTLIGHT_RADIUS * 0.5;
    const fadeDistance = SPOTLIGHT_RADIUS * 0.75;

    // Skip the whole effect on touch / coarse-pointer devices (no cursor).
    const finePointer = window.matchMedia('(pointer: fine)').matches;

    // rAF-throttle: process at most once per frame, and split DOM reads from
    // writes so we don't thrash layout on every mousemove event.
    let lastX = 0, lastY = 0, pending = false;

    const process = () => {
      pending = false;
      const sp = spotlightRef.current;
      if (!sp) return;
      const cards = document.querySelectorAll<HTMLElement>('.magic-bento-card');
      // Phase 1: read all rects.
      const reads: { card: HTMLElement; rect: DOMRect }[] = [];
      cards.forEach(card => reads.push({ card, rect: card.getBoundingClientRect() }));
      // Phase 2: compute + write.
      let minDistance = Infinity;
      for (const { card, rect } of reads) {
        if (rect.bottom < -200 || rect.top > window.innerHeight + 200) continue; // offscreen
        const relativeX = ((lastX - rect.left) / rect.width) * 100;
        const relativeY = ((lastY - rect.top) / rect.height) * 100;
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        const effectiveDistance = Math.max(0,
          Math.hypot(lastX - centerX, lastY - centerY) - Math.max(rect.width, rect.height) / 2);
        minDistance = Math.min(minDistance, effectiveDistance);
        let glowIntensity = 0;
        if (effectiveDistance <= proximity) glowIntensity = 1;
        else if (effectiveDistance <= fadeDistance)
          glowIntensity = (fadeDistance - effectiveDistance) / (fadeDistance - proximity);
        card.style.setProperty('--glow-x', `${relativeX}%`);
        card.style.setProperty('--glow-y', `${relativeY}%`);
        card.style.setProperty('--glow-intensity', glowIntensity.toString());
        card.style.setProperty('--glow-radius', `${SPOTLIGHT_RADIUS}px`);
      }
      gsap.to(sp, { left: lastX, top: lastY, duration: 0.1, ease: 'power2.out' });
      const targetOpacity =
        minDistance <= proximity ? 0.8
          : minDistance <= fadeDistance
            ? ((fadeDistance - minDistance) / (fadeDistance - proximity)) * 0.8 : 0;
      gsap.to(sp, { opacity: targetOpacity, duration: targetOpacity > 0 ? 0.2 : 0.5, ease: 'power2.out' });
    };

    const handleMouseMove = (e: MouseEvent) => {
      lastX = e.clientX; lastY = e.clientY;
      if (!pending) { pending = true; requestAnimationFrame(process); }
    };
    if (!finePointer) return; // don't attach listeners on touch devices

    const handleMouseLeave = () => {
      document.querySelectorAll<HTMLElement>('.magic-bento-card').forEach(card => {
        card.style.setProperty('--glow-intensity', '0');
      });
      if (spotlightRef.current) {
        gsap.to(spotlightRef.current, { opacity: 0, duration: 0.3, ease: 'power2.out' });
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseleave', handleMouseLeave);
      spotlightRef.current?.parentNode?.removeChild(spotlightRef.current);
    };
  }, []);

  return null;
}
