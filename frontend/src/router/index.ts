import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'workbench',
      component: () => import('../views/WorkbenchView.vue'),
    },
    {
      path: '/tools',
      redirect: { name: 'workbench' },
    },
  ],
})

export default router
