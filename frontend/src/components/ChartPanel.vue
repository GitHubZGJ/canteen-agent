<script setup lang="ts">
import * as echarts from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{ option: echarts.EChartsOption; height?: string }>()
const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

function resize() {
  chart?.resize()
}

onMounted(() => {
  chart = echarts.init(el.value!)
  chart.setOption(props.option)
  window.addEventListener('resize', resize)
})

watch(
  () => props.option,
  (opt) => chart?.setOption(opt, true),
  { deep: true },
)

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
})
</script>

<template>
  <div ref="el" :style="{ height: height || '320px', width: '100%' }" />
</template>