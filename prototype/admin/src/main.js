import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'

import App from './App.vue'
import DoctorsView from './views/DoctorsView.vue'
import PricesView from './views/PricesView.vue'
import UploadView from './views/UploadView.vue'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/prices' },
    { path: '/prices', component: PricesView, meta: { title: 'Prices' } },
    { path: '/doctors', component: DoctorsView, meta: { title: 'Doctors' } },
    { path: '/upload', component: UploadView, meta: { title: 'Upload price sheet' } },
  ],
})

router.afterEach((to) => {
  document.title = `${to.meta.title} · RateCard Admin`
})

createApp(App).use(router).mount('#app')
