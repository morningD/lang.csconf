/**
 * Post-build script: generate static HTML pages for each route.
 *
 * Why: Baidu spider cannot render JavaScript. Without static HTML,
 * it sees a blank page. This script creates a real HTML file per route
 * with correct <title>, <meta>, OG tags, and JSON-LD so search engines
 * can index every page even without JS execution.
 *
 * Strategy:
 * - Copy dist/index.html → conference/{ID}/index.html with per-page meta tags
 * - Copy dist/index.html → 404.html for SPA fallback on GitHub Pages
 * - Top conferences get rich descriptions; others get a generic conference template
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const SITE_URL = 'https://morningd.github.io/lang.csconf'

// Map category codes to full names for descriptions
const CATEGORY_NAMES = {
  AI: 'Artificial Intelligence',
  DB: 'Database / Data Mining / Information Retrieval',
  NW: 'Computer Networking',
  SE: 'Software Engineering / Programming Languages',
  CG: 'Computer Graphics & Multimedia',
  CT: 'Theory of Computation',
  HI: 'Human-Computer Interaction',
  SC: 'Network & Information Security',
  DS: 'Computer Architecture / Systems',
  MX: 'Interdisciplinary & Emerging',
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

/**
 * Inject SEO meta tags into the base HTML for a specific page.
 */
function buildPageHtml(baseHtml, { title, description, path, jsonLd }) {
  let html = baseHtml

  // Replace <title>
  html = html.replace(
    /<title>.*?<\/title>/,
    `<title>${escapeHtml(title)}</title>`
  )

  // Replace meta description
  html = html.replace(
    /<meta\s+name="description"\s+content="[^"]*"/,
    `<meta name="description" content="${escapeHtml(description)}"`
  )

  // Replace OG tags
  html = html.replace(
    /<meta\s+property="og:title"\s+content="[^"]*"/,
    `<meta property="og:title" content="${escapeHtml(title)}"`
  )
  html = html.replace(
    /<meta\s+property="og:description"\s+content="[^"]*"/,
    `<meta property="og:description" content="${escapeHtml(description)}"`
  )
  html = html.replace(
    /<meta\s+property="og:url"\s+content="[^"]*"/,
    `<meta property="og:url" content="${SITE_URL}${path}"`
  )

  // Replace Twitter tags
  html = html.replace(
    /<meta\s+name="twitter:title"\s+content="[^"]*"/,
    `<meta name="twitter:title" content="${escapeHtml(title)}"`
  )
  html = html.replace(
    /<meta\s+name="twitter:description"\s+content="[^"]*"/,
    `<meta name="twitter:description" content="${escapeHtml(description)}"`
  )

  // Replace canonical
  html = html.replace(
    /<link\s+rel="canonical"\s+href="[^"]*"/,
    `<link rel="canonical" href="${SITE_URL}${path}"`
  )

  // Replace JSON-LD
  if (jsonLd) {
    html = html.replace(
      /<script\s+type="application\/ld\+json">[\s\S]*?<\/script>/,
      `<script type="application/ld+json">\n${JSON.stringify(jsonLd, null, 2)}\n</script>`
    )
  }

  return html
}

function main() {
  const distDir = resolve(__dirname, '..', 'dist')

  if (!existsSync(resolve(distDir, 'index.html'))) {
    console.error('[prerender] dist/index.html not found. Run "pnpm build" first.')
    process.exit(1)
  }

  const baseHtml = readFileSync(resolve(distDir, 'index.html'), 'utf-8')
  let conferences = []

  try {
    const indexPath = resolve(__dirname, '..', 'public', 'data', 'stats', 'conferences_index.json')
    conferences = JSON.parse(readFileSync(indexPath, 'utf-8'))
  } catch {
    console.warn('[prerender] Could not read conferences_index.json, skipping conference pages')
  }

  let count = 0

  // Generate conference detail pages
  for (const conf of conferences) {
    const dir = resolve(distDir, 'conference', conf.id)
    mkdirSync(dir, { recursive: true })

    const catName = CATEGORY_NAMES[conf.category] || conf.category
    const title = `${conf.title} (${conf.id}) Language Diversity — lang.csconf`
    const description =
      `${conf.title} (${catName}, CCF-${conf.rank}): ${conf.total_papers.toLocaleString()} papers analyzed. ` +
      `Dominant first-author language: ${conf.dominant_language} (${conf.dominant_pct}%). ` +
      `Data from 2010 to ${conf.latest_year}.`

    const jsonLd = {
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      name: title,
      description: description,
      url: `${SITE_URL}/conference/${conf.id}`,
      isPartOf: {
        '@type': 'WebSite',
        name: 'lang.csconf',
        url: SITE_URL,
      },
      about: {
        '@type': 'EventSeries',
        name: conf.description,
      },
    }

    const pageHtml = buildPageHtml(baseHtml, {
      title,
      description,
      path: `/conference/${conf.id}`,
      jsonLd,
    })

    writeFileSync(resolve(dir, 'index.html'), pageHtml)
    count++
  }

  // Generate 404.html (SPA fallback for GitHub Pages)
  const html404 = buildPageHtml(baseHtml, {
    title: 'Page Not Found — lang.csconf',
    description: 'Visualizing the linguistic diversity of first authors across 416 CCF-rated computer science conferences.',
    path: '',
    jsonLd: null,
  })
  writeFileSync(resolve(distDir, '404.html'), html404)

  console.log(`[prerender] Generated ${count} conference pages + 404.html`)
}

main()
