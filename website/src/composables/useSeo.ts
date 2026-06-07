import { useHead } from '@unhead/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const SITE_URL = 'https://morningd.github.io/lang.csconf'
const SITE_NAME = 'lang.csconf'
const DEFAULT_DESCRIPTION =
  'Analyzing 908K+ first authors across 416 CCF-rated CS conferences (2010–2026). Explore author language diversity, top institution trends, and acceptance rates.'

export function useSeo(options?: {
  title?: string
  description?: string
  path?: string
}) {
  const { t } = useI18n()

  const fullTitle = computed(() => {
    const pageTitle = options?.title || t('site.title')
    return `${pageTitle} — ${SITE_NAME}`
  })

  const description = options?.description || DEFAULT_DESCRIPTION
  const canonicalUrl = `${SITE_URL}${options?.path || ''}`

  useHead({
    title: fullTitle,
    meta: [
      { name: 'description', content: description },
      { property: 'og:type', content: 'website' },
      { property: 'og:title', content: fullTitle },
      { property: 'og:description', content: description },
      { property: 'og:url', content: canonicalUrl },
      { property: 'og:image', content: `${SITE_URL}/lang.csconf/favicon.svg` },
      { property: 'og:site_name', content: SITE_NAME },
      { property: 'og:locale', content: 'en_US' },
      { property: 'og:locale:alternate', content: 'zh_CN' },
      { name: 'twitter:card', content: 'summary' },
      { name: 'twitter:title', content: fullTitle },
      { name: 'twitter:description', content: description },
    ],
    link: [{ rel: 'canonical', href: canonicalUrl }],
  })
}
