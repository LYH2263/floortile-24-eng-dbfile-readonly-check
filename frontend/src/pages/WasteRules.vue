<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'
const settings = ref({})
onMounted(async () => { settings.value = await getJSON('/api/settings') })
</script>
<template>
  <div class="page">
    <h1>损耗规则</h1>
    <p>默认损耗率按面积法向上取整后再乘 (1+损耗%)。</p>
    <p>当前默认损耗：<strong>{{ settings.waste_pct }}%</strong></p>
    <p>网格预览块数可能大于面积法片数，下单以面积法 order_count 为准。</p>
  </div>
</template>
