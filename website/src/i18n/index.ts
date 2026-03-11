import { createI18n } from 'vue-i18n'

import en from './locales/en.json'
import zh from './locales/zh.json'
import ja from './locales/ja.json'
import de from './locales/de.json'

const supportedLocales: string[] = ['en', 'zh', 'ja', 'de']
const savedLocale = typeof localStorage !== 'undefined' ? localStorage.getItem('lang-csconf-locale') : null
const browserLang = typeof navigator !== 'undefined' ? (navigator.language.split('-')[0] ?? 'en') : 'en'

function resolveLocale(): string {
  if (savedLocale && supportedLocales.includes(savedLocale)) return savedLocale
  if (supportedLocales.includes(browserLang)) return browserLang
  return 'en'
}
const defaultLocale = resolveLocale()

const i18n = createI18n({
  legacy: false,
  locale: defaultLocale,
  fallbackLocale: 'en',
  messages: {
    en,
    zh,
    ja,
    de,
  },
})

export default i18n
