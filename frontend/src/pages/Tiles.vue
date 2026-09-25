<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'
const items = ref([])
onMounted(async () => { items.value = (await getJSON('/api/tiles')).items })
</script>
<template>
  <div class="page">
    <h1>砖型库</h1>
    <div class="tile-cards">
      <div v-for="t in items" :key="t.id" class="tile-card" :class="{ dirty: t.data_quality === 'dirty' }">
        <strong>{{ t.name }}</strong>
        <span>{{ t.tile_l }} × {{ t.tile_w }} m</span>
        <em v-if="t.data_quality === 'dirty'">无效规格</em>
      </div>
    </div>
  </div>
</template>
