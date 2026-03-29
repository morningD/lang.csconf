<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

const { t, locale } = useI18n()
const route = useRoute()
const menuOpen = ref(false)

const languages = [
  { code: 'en', label: 'English' },
  { code: 'zh', label: '中文' },
  { code: 'ja', label: '日本語' },
  { code: 'de', label: 'Deutsch' },
]

function setLocale(code: string) {
  locale.value = code
  localStorage.setItem('lang-csconf-locale', code)
}

const navItems = [
  { path: '/', key: 'nav.home' },
  { path: '/compare', key: 'nav.compare' },
  { path: '/trends', key: 'nav.trends' },
  { path: '/about', key: 'nav.about' },
]
</script>

<template>
  <header class="app-header fixed top-0 left-0 right-0 z-50 bg-gray-900/80 backdrop-blur-md border-b border-gray-700/50">
    <div class="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
      <!-- Logo -->
      <router-link to="/" class="flex items-center gap-2 text-white font-bold text-lg no-underline hover:opacity-80 transition-opacity">
        <span class="text-xl">🗣️</span>
        <span class="hidden sm:inline">lang.csconf</span>
      </router-link>

      <!-- Desktop Nav -->
      <nav class="hidden md:flex items-center gap-1">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="px-3 py-1.5 rounded-lg text-sm text-gray-300 no-underline hover:text-white hover:bg-gray-700/50 transition-all"
          :class="{ 'text-white bg-gray-700/50': route.path === item.path }"
        >
          {{ t(item.key) }}
        </router-link>
      </nav>

      <!-- Language Switcher + GitHub + Mobile Menu -->
      <div class="flex items-center gap-2">
        <a
          href="https://github.com/morningD/lang.csconf"
          target="_blank"
          rel="noopener noreferrer"
          class="text-gray-400 hover:text-white transition-colors p-1.5"
          title="GitHub"
        >
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
          </svg>
        </a>
        <select
          :value="locale"
          @change="setLocale(($event.target as HTMLSelectElement).value)"
          class="bg-gray-800 text-gray-300 text-sm rounded-lg px-2 py-1 border border-gray-600 cursor-pointer"
        >
          <option v-for="lang in languages" :key="lang.code" :value="lang.code">
            {{ lang.label }}
          </option>
        </select>

        <!-- Mobile hamburger -->
        <button
          class="md:hidden p-2 text-gray-300 hover:text-white"
          @click="menuOpen = !menuOpen"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path v-if="!menuOpen" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
            <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Mobile Menu -->
    <div v-if="menuOpen" class="md:hidden bg-gray-900/95 border-t border-gray-700/50">
      <nav class="flex flex-col p-4 gap-1">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="px-3 py-2 rounded-lg text-gray-300 no-underline hover:text-white hover:bg-gray-700/50"
          @click="menuOpen = false"
        >
          {{ t(item.key) }}
        </router-link>
      </nav>
    </div>
  </header>
</template>
