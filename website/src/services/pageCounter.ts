import type { Router } from 'vue-router'

const COUNTER_URL = 'https://page-counter.duanmoming.workers.dev/v1/pageviews'
const SITE = 'lang-csconf'

let lastTrackedPath: string | null = null
let currentCount: number | null = null
const listeners = new Set<(count: number | null) => void>()

function notify() {
  for (const listener of listeners) listener(currentCount)
}

function deploymentPath(routePath: string) {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '')
  const path = routePath === '/' ? '' : routePath.replace(/\/$/, '')
  return `${base}${path}` || '/'
}

async function track(path: string) {
  if (path === lastTrackedPath) return
  lastTrackedPath = path
  try {
    const response = await fetch(COUNTER_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ site: SITE, path }),
      keepalive: true,
    })
    if (!response.ok) return
    const data = await response.json() as { count?: unknown }
    if (typeof data.count === 'number') {
      currentCount = data.count
      notify()
    }
  } catch {
    // Counter availability must never affect navigation or rendering.
  }
}

export function installPageCounter(router: Router) {
  router.afterEach((to, _from, failure) => {
    if (!failure) void track(deploymentPath(to.path))
  })
  router.isReady().then(() => void track(deploymentPath(router.currentRoute.value.path)))
}

export function subscribeToPageCount(listener: (count: number | null) => void) {
  listeners.add(listener)
  listener(currentCount)
  return () => listeners.delete(listener)
}
