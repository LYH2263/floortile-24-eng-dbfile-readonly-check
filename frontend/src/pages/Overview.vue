<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'

const rooms = ref([])
const tiles = ref([])
onMounted(async () => {
  rooms.value = (await getJSON('/api/rooms')).items
  tiles.value = (await getJSON('/api/tiles')).items
})
</script>
<template>
  <div class="page">
    <h1>面积概览</h1>
    <p>干净房间 {{ rooms.filter(r => r.data_quality === 'clean').length }} 间，待修正 {{ rooms.filter(r => r.data_quality === 'dirty').length }} 间。</p>
    <div class="cards">
      <article v-for="r in rooms" :key="r.id" :class="{ dirty: r.data_quality === 'dirty' }">
        <h3>{{ r.name }}</h3>
        <p>{{ r.length }} × {{ r.width }} m</p>
      </article>
    </div>
    <h2>砖型</h2>
    <p>{{ tiles.length }} 种规格在库</p>
  </div>
</template>
