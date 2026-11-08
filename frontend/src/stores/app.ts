import { defineStore } from 'pinia'

// 全局日期区间：看板加载后写入，菜品分析页沿用
export const useAppStore = defineStore('app', {
  state: () => ({ start: '', end: '' }),
  actions: {
    setRange(start: string, end: string) {
      this.start = start
      this.end = end
    },
  },
})