<template>
  <div id="app">
    <el-container>
      <el-header>
        <h1>📊 TradingAgents-CN 数据同步中心</h1>
      </el-header>
      <el-main>
        <DataSync />
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import DataSync from './views/DataSync.vue'
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  margin: 0;
  padding: 0;
}

.el-header {
  background-color: #409EFF;
  color: white;
  text-align: center;
  line-height: 60px;
  padding: 0;
}

.el-main {
  padding: 20px;
}
</style>
