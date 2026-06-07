import { ref, watch } from 'vue'

/**
 * Animated counter: counts from 0 to `target` over `duration` ms.
 * Returns a ref that updates on each animation frame.
 */
export function useCountUp(target: () => number, duration = 1000) {
  const display = ref(0)
  let rafId = 0

  function animate(to: number) {
    cancelAnimationFrame(rafId)
    if (to === 0) {
      display.value = 0
      return
    }
    const from = display.value
    const start = performance.now()
    const diff = to - from

    function tick(now: number) {
      const elapsed = now - start
      const progress = Math.min(elapsed / duration, 1)
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3)
      display.value = Math.round(from + diff * eased)
      if (progress < 1) {
        rafId = requestAnimationFrame(tick)
      }
    }

    rafId = requestAnimationFrame(tick)
  }

  watch(target, (val) => animate(val), { immediate: true })

  return display
}
