<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <footer class="app-footer relative bg-gray-900 border-t border-gray-700/50 mt-auto">
    <div class="relative z-10 max-w-7xl mx-auto px-4 py-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-gray-400 text-sm">
      <div class="flex items-center gap-2">
        <span>🗣️ lang.csconf</span>
        <span class="text-gray-600">|</span>
        <span>Apache-2.0</span>
      </div>
      <div class="flex items-center gap-4">
        <a
          href="https://github.com/morningD/lang.csconf"
          target="_blank"
          rel="noopener noreferrer"
          class="text-gray-400 hover:text-white transition-colors no-underline"
        >
          GitHub
        </a>
        <a
          href="https://dblp.org"
          target="_blank"
          rel="noopener noreferrer"
          class="text-gray-400 hover:text-white transition-colors no-underline"
        >
          Data: DBLP
        </a>
        <span class="text-gray-600">|</span>
        <span class="text-gray-500 text-xs">
          👀 <span id="busuanzi_value_site_pv">-</span> views
          · <span id="busuanzi_value_site_uv">-</span> visitors
        </span>
      </div>
    </div>
  </footer>
</template>
