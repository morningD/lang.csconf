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
          <p class="text-gray-400 text-sm mb-3">{{ t('about.data_sources_papers') }}</p>
          <ul class="space-y-3 text-gray-300">
            <li class="flex items-start gap-2">
              <span class="text-blue-400 mt-1">•</span>
              <div>
                <a href="https://dblp.org" target="_blank" rel="noopener" class="text-blue-400 hover:underline">DBLP</a>
                — {{ t('about.src_dblp') }}
              </div>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-blue-400 mt-1">•</span>
              <div>
                <a href="https://www.ccf.org.cn/Academic_Evaluation/By_category/" target="_blank" rel="noopener" class="text-blue-400 hover:underline">CCF Recommended Lists</a>
                — {{ t('about.src_ccf_pdf') }}
              </div>
            </li>
          </ul>
          <p class="text-gray-400 text-sm mt-4 mb-3">{{ t('about.data_sources_classifier') }}</p>
          <ul class="space-y-3 text-gray-300">
            <li class="flex items-start gap-2">
              <span class="text-blue-400 mt-1">•</span>
              <div>
                <a href="https://github.com/zafercavdar/fasttext-langdetect" target="_blank" rel="noopener" class="text-blue-400 hover:underline">fast-langdetect</a>
                — {{ t('about.src_fasttext') }}
              </div>
            </li>
          </ul>
          <p class="text-gray-400 text-sm mt-4 mb-3">{{ t('about.data_sources_accept') }}</p>
          <ul class="space-y-3 text-gray-300">
            <li class="flex items-start gap-2">
              <span class="text-blue-400 mt-1">•</span>
              <div>
                <a href="https://github.com/ccfddl/ccf-deadlines" target="_blank" rel="noopener" class="text-blue-400 hover:underline">CCF Deadlines</a>
              </div>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-blue-400 mt-1">•</span>
              <div>
                <a href="https://github.com/Xovee/cs-conf-stats" target="_blank" rel="noopener" class="text-blue-400 hover:underline">cs-conf-stats</a>
                (Xovee)
              </div>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-blue-400 mt-1">•</span>
              <div>
                <a href="https://github.com/emeryberger/csconferences" target="_blank" rel="noopener" class="text-blue-400 hover:underline">csconferences</a>
                (Emery Berger)
              </div>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-blue-400 mt-1">•</span>
              <div>
                <a href="https://github.com/lixin4ever/Conference-Acceptance-Rate" target="_blank" rel="noopener" class="text-blue-400 hover:underline">Conference-Acceptance-Rate</a>
                (lixin4ever)
              </div>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-blue-400 mt-1">•</span>
              <div>
                <a href="https://github.com/puzhuoliu/Computer-Security-Conference-Acceptance-Rate" target="_blank" rel="noopener" class="text-blue-400 hover:underline">Security Conference Acceptance Rate</a>
                (puzhuoliu)
              </div>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-blue-400 mt-1">•</span>
              <div>
                <a href="https://www.conferences-computer.science/" target="_blank" rel="noopener" class="text-blue-400 hover:underline">conferences-computer.science</a>
              </div>
            </li>
          </ul>
        </section>

        <!-- Credits -->
        <section class="card p-6 bg-gray-800/50 border-gray-700/50">
          <h2 class="text-xl font-semibold text-white mb-3">{{ t('about.credits') }}</h2>
          <ul class="space-y-2 text-gray-300">
            <li>Built with Vue 3, Vite, ECharts, UnoCSS</li>
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
