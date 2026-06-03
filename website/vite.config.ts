import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import UnoCSS from 'unocss/vite'
import { readFileSync, writeFileSync } from 'fs'
import { resolve } from 'path'

const SITE_URL = 'https://morningd.github.io/lang.csconf'
const STATIC_PAGES = ['', '/compare', '/trends', '/about']

function sitemapPlugin(): Plugin {
  return {
    name: 'sitemap-generator',
    closeBundle() {
      const publicDir = resolve(process.cwd(), 'public')
      const indexPath = resolve(publicDir, 'data/stats/conferences_index.json')

      let conferences: { id: string }[] = []
      try {
        conferences = JSON.parse(readFileSync(indexPath, 'utf-8'))
      } catch {
        console.warn('[sitemap] Could not read conferences_index.json')
      }

      const urls = [
        ...STATIC_PAGES.map((p) => ({
          loc: `${SITE_URL}${p}`,
          changefreq: 'weekly' as const,
          priority: p === '' ? '1.0' : '0.8',
        })),
        ...conferences.map((c) => ({
          loc: `${SITE_URL}/conference/${c.id}`,
          changefreq: 'monthly' as const,
          priority: '0.6',
        })),
      ]

      const xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ...urls.map(
          (u) =>
            `  <url>\n    <loc>${u.loc}</loc>\n    <changefreq>${u.changefreq}</changefreq>\n    <priority>${u.priority}</priority>\n  </url>`
        ),
        '</urlset>',
      ].join('\n')

      writeFileSync(resolve(publicDir, 'sitemap.xml'), xml)
      console.log(`[sitemap] Generated ${urls.length} URLs → public/sitemap.xml`)
    },
  }
}

export default defineConfig({
  base: '/lang.csconf/',
  plugins: [vue(), UnoCSS(), sitemapPlugin()],
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ['echarts', 'vue-echarts'],
          'vue-vendor': ['vue', 'vue-router', 'vue-i18n'],
        },
      },
    },
  },
})
