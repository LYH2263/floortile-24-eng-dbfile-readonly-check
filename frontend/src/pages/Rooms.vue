<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'
const items = ref([])
onMounted(async () => { items.value = (await getJSON('/api/rooms')).items })
</script>
<template>
  <div class="page">
    <h1>房间档案</h1>
    <table class="tbl">
      <thead><tr><th>名称</th><th>长×宽</th><th>质量</th><th></th></tr></thead>
      <tbody>
        <tr v-for="r in items" :key="r.id">
          <td>{{ r.name }}</td>
          <td>{{ r.length }} × {{ r.width }}</td>
          <td :class="r.data_quality">{{ r.data_quality === 'clean' ? '正常' : '脏数据' }}</td>
          <td><router-link :to="`/rooms/${r.id}`">详情</router-link></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
