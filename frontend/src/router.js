import { createRouter, createWebHistory } from 'vue-router'
import Overview from './pages/Overview.vue'
import Rooms from './pages/Rooms.vue'
import RoomDetail from './pages/RoomDetail.vue'
import Tiles from './pages/Tiles.vue'
import Bench from './pages/Bench.vue'
import WasteRules from './pages/WasteRules.vue'
import History from './pages/History.vue'
import Settings from './pages/Settings.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Overview },
    { path: '/rooms', component: Rooms },
    { path: '/rooms/:id', component: RoomDetail, props: true },
    { path: '/tiles', component: Tiles },
    { path: '/bench', component: Bench },
    { path: '/waste', component: WasteRules },
    { path: '/history', component: History },
    { path: '/settings', component: Settings },
  ],
})
