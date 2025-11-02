
<template>
  <div>
    <el-button type="primary" @click="syncData" :loading="loading">
      🔁 同步A股基础数据
    </el-button>
    <el-table :data="stockData" style="width: 100%">
      <el-table-column label="股票代码" prop="ts_code" />
      <el-table-column label="股票名称" prop="name" />
      <el-table-column label="行业" prop="industry" />
    </el-table>
    <el-alert v-if="message" :title="message" type="info" />
  </div>
</template>

<script setup>
import { ref } from "vue";
import axios from "axios";
import { ElButton, ElTable, ElTableColumn, ElAlert } from "element-plus";

const stockData = ref([]);
const loading = ref(false);
const message = ref("");

const syncData = async () => {
  loading.value = true;
  message.value = "正在同步数据，请稍候...";
  try {
    const response = await axios.post("http://localhost:8000/api/data_sync");
    message.value = response.data.message;
    loading.value = false;
  } catch (error) {
    message.value = "❌ 数据同步失败：" + error.response?.data?.message;
    loading.value = false;
  }
};

const fetchStockData = async () => {
  try {
    const response = await axios.get("http://localhost:8000/api/stock/basic");
    stockData.value = response.data.data;
  } catch (error) {
    console.error("获取股票数据失败", error);
  }
};

fetchStockData();  // 初始化时拉取数据
</script>

<style>
#app {
  padding: 20px;
}
</style>
