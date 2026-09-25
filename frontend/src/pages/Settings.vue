<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'
const settings = ref({})
onMounted(async () => { settings.value = await getJSON('/api/settings') })
</script>
<template>
  <div class="page">
    <h1>参数</h1>
    <ul>
      <li v-for="(v, k) in settings" :key="k">{{ k }}：{{ v }}</li>
    </ul>
  </div>
</template>
