<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div class="min-h-screen py-8 px-4">
    <div class="max-w-3xl mx-auto">
      <h1 class="text-3xl font-bold text-white mb-8">{{ t('about.title') }}</h1>

      <div class="space-y-8">
        <!-- Methodology -->
        <section class="card p-6 bg-gray-800/50 border-gray-700/50">
          <h2 class="text-xl font-semibold text-white mb-3">{{ t('about.methodology') }}</h2>
          <p class="text-gray-300 leading-relaxed">{{ t('about.methodology_text') }}</p>
        </section>

        <!-- Disclaimer -->
        <section class="card p-6 bg-yellow-900/20 border-yellow-700/30">
          <h2 class="text-xl font-semibold text-yellow-400 mb-3">{{ t('about.disclaimer') }}</h2>
          <p class="text-gray-300 leading-relaxed">{{ t('about.disclaimer_text') }}</p>
        </section>

        <!-- Accuracy -->
        <section class="card p-6 bg-gray-800/50 border-gray-700/50">
          <h2 class="text-xl font-semibold text-white mb-3">{{ t('about.accuracy') }}</h2>
          <p class="text-gray-300 leading-relaxed">{{ t('about.accuracy_text') }}</p>
        </section>

        <!-- Data Sources -->
        <section class="card p-6 bg-gray-800/50 border-gray-700/50">
          <h2 class="text-xl font-semibold text-white mb-3">{{ t('about.data_sources') }}</h2>
          <ul class="space-y-3 text-gray-300">
            <li class="flex items-start gap-2">
              <span class="text-blue-400 mt-1">•</span>
              <div>
                <a href="https://dblp.org" target="_blank" rel="noopener" class="text-blue-400 hover:underline">DBLP</a>
                — Computer science bibliography for author and publication data
              </div>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-blue-400 mt-1">•</span>
              <div>
                <a href="https://github.com/ccfddl/ccf-deadlines" target="_blank" rel="noopener" class="text-blue-400 hover:underline">CCF Deadlines</a>
                — Conference list and CCF rankings
              </div>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-blue-400 mt-1">•</span>
              <div>
                <strong>name2nat</strong> — Name-to-nationality prediction library
              </div>
            </li>
          </ul>
        </section>

        <!-- Credits -->
        <section class="card p-6 bg-gray-800/50 border-gray-700/50">
          <h2 class="text-xl font-semibold text-white mb-3">{{ t('about.credits') }}</h2>
          <ul class="space-y-2 text-gray-300">
            <li>Built with Vue 3, Vite, ECharts, UnoCSS</li>

            <li>Inspired by <a href="https://ccfddl.github.io" target="_blank" rel="noopener" class="text-blue-400 hover:underline">ccfddl</a></li>
          </ul>
        </section>

        <!-- License -->
        <section class="card p-6 bg-gray-800/50 border-gray-700/50">
          <h2 class="text-xl font-semibold text-white mb-3">{{ t('about.license') }}</h2>
          <p class="text-gray-300">
            This project is licensed under the
            <a href="https://github.com/morningD/lang.csconf/blob/main/LICENSE" target="_blank" rel="noopener" class="text-blue-400 hover:underline">Apache License 2.0</a>.
          </p>
        </section>
      </div>
    </div>
  </div>
</template>
