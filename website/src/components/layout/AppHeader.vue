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

      <!-- Language Switcher + Mobile Menu -->
      <div class="flex items-center gap-2">
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
