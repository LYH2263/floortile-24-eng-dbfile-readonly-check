<script setup>
</script>
<template>
  <div class="ft-shell">
    <aside class="ft-rail">
      <div class="ft-brand">铺地砖助手</div>
      <router-link to="/">面积概览</router-link>
      <router-link to="/rooms">房间档案</router-link>
      <router-link to="/tiles">砖型库</router-link>
      <router-link to="/bench">下单测算</router-link>
      <router-link to="/waste">损耗规则</router-link>
      <router-link to="/history">测算记录</router-link>
      <router-link to="/settings">参数</router-link>
      <div class="ft-grid-deco" aria-hidden="true"></div>
    </aside>
    <main class="ft-main">
      <router-view />
    </main>
  </div>
</template>
