<script setup lang="ts">
import { defineAsyncComponent } from 'vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppFooter from '@/components/layout/AppFooter.vue'

const PixelRobots = defineAsyncComponent(() => import('@/components/layout/PixelRobots.vue'))
</script>

<template>
  <div class="min-h-screen bg-gray-950 text-gray-100 flex flex-col overflow-x-hidden">
    <AppHeader />
    <main class="flex-1 pt-14 pb-48">
      <RouterView />
    </main>
    <AppFooter />
    <PixelRobots />
  </div>
</template>
