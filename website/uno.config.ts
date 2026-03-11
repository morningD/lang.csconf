import { defineConfig, presetUno, presetAttributify } from 'unocss'
import transformerDirectives from '@unocss/transformer-directives'

export default defineConfig({
  presets: [
    presetUno(),
    presetAttributify(),
  ],
  transformers: [
    transformerDirectives(),
  ],
  shortcuts: {
    'btn': 'px-4 py-2 rounded-lg font-medium transition-all duration-200 cursor-pointer',
    'btn-primary': 'btn bg-blue-500 text-white hover:bg-blue-600',
    'card': 'bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700',
    'section-title': 'text-2xl font-bold text-gray-900 dark:text-white',
  },
  theme: {
    colors: {
      primary: {
        50: '#eff6ff',
        100: '#dbeafe',
        200: '#bfdbfe',
        300: '#93c5fd',
        400: '#60a5fa',
        500: '#3b82f6',
        600: '#2563eb',
        700: '#1d4ed8',
        800: '#1e40af',
        900: '#1e3a8a',
      },
    },
  },
})
