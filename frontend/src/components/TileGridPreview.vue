<script setup>
defineProps({
  cols: { type: Number, default: 0 },
  rows: { type: Number, default: 0 },
  gridCount: { type: Number, default: 0 },
})
</script>
<template>
  <div class="grid-preview">
    <p>铺砖网格预览：{{ cols }} 列 × {{ rows }} 行，共 {{ gridCount }} 块（含裁切格）</p>
    <div class="mini-grid" :style="{ gridTemplateColumns: `repeat(${Math.min(cols, 12)}, 1fr)` }">
      <span v-for="n in Math.min(cols * rows, 48)" :key="n" class="cell"></span>
    </div>
  </div>
</template>
