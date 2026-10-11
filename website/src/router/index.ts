import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
  },
  {
    path: '/conference/:id',
    name: 'conference',
    component: () => import('@/views/ConferenceView.vue'),
  },
  {
    path: '/conference/:id/finances',
    name: 'conference-finances',
    component: () => import('@/views/FinancesView.vue'),
  },
  {
    path: '/compare',
    name: 'compare',
    component: () => import('@/views/CompareView.vue'),
  },
  {
    path: '/trends',
    name: 'trends',
    component: () => import('@/views/TrendsView.vue'),
  },
  {
    path: '/about',
    name: 'about',
    component: () => import('@/views/AboutView.vue'),
  },
  {
    path: '/organizers',
    name: 'organizers',
    component: () => import('@/views/OrganizersView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router
