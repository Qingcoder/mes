import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import Vant from 'vant'
import './styles/reset.css'
import 'vant/lib/index.css'
import App from './App.vue'
import { getToken, getPermissions } from './api'
import { installPlainTextCopy } from './utils/plainCopy'
import { stopSpeak } from './utils/voice'
import {
  APP_ROUTES, validateRouteConfig, findAppRoute, isPublicRoute, firstAllowedPath,
} from './router/routeConfig'
import './style.css'

validateRouteConfig()
installPlainTextCopy()

const router = createRouter({
  history: createWebHistory(),
  routes: APP_ROUTES.map(r => ({
    path: r.path,
    name: r.name,
    component: r.component,
    redirect: r.redirect,
    meta: {
      permission: r.permission, public: !!r.public, menu: !!r.menu,
      label: r.label || '', fixed: !!r.fixed, hideIcon: !!r.hideIcon, description: r.description || '',
    },
  })) as any,
})

router.beforeEach((to, _from, next) => {
  if (!to.path.startsWith('/station')) stopSpeak()
  if (!isPublicRoute(to.path) && !getToken()) {
    return next({ path: '/login', query: { redirect: to.fullPath } })
  }
  const perms = getPermissions()
  const config = findAppRoute(to.path)
  if (config?.permission && perms.length && !perms.includes(config.permission)) {
    return next({ path: firstAllowedPath(perms), query: { denied: config.label || '该功能' } })
  }
  next()
})

createApp(App).use(router).use(Vant).mount('#app')
