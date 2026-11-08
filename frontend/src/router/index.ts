import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('../views/LoginView.vue') },
    {
      path: '/',
      component: () => import('../layouts/MainLayout.vue'),
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          component: () => import('../views/DashboardView.vue'),
          meta: { title: '经营大屏' },
        },
        {
          path: 'dishes',
          component: () => import('../views/DishesView.vue'),
          meta: { title: '菜品分析' },
        },
        {
          path: 'forecast',
          component: () => import('../views/ForecastView.vue'),
          meta: { title: '预测备餐' },
        },
        {
          path: 'optimization',
          component: () => import('../views/OptimizationView.vue'),
          meta: { title: '菜单优化' },
        },
        {
          path: 'agent',
          component: () => import('../views/AgentView.vue'),
          meta: { title: '智能助手' },
        },
        {
          path: 'suggestions',
          component: () => import('../views/SuggestionsView.vue'),
          meta: { title: '建议工单' },
        },
        {
          path: 'reports',
          component: () => import('../views/ReportsView.vue'),
          meta: { title: '报告中心' },
        },
        {
          path: 'data',
          component: () => import('../views/DataView.vue'),
          meta: { title: '数据管理' },
        },
      ],
    },
  ],
})

router.beforeEach((to) => {
  if (to.path !== '/login' && !localStorage.getItem('token')) return '/login'
})

export default router