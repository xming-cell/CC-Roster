<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'

import { useToolsStore } from '../stores/tools'
import { useUsageStore } from '../stores/usage'
import {
  dailyUsage,
  formatCost,
  formatDate,
  formatInteger,
  formatTokens,
} from '../utils/usageDisplay'

const usage = useUsageStore()
const toolsStore = useToolsStore()
const { data, days, loading, loaded, error } = storeToRefs(usage)
const { tools } = storeToRefs(toolsStore)

const ranges = [7, 30, 90]
const chartDays = computed(() => dailyUsage(data.value?.records ?? []).slice(-14))
const maxCalls = computed(() => Math.max(1, ...chartDays.value.map((day) => day.calls)))
const chartToolIds = computed(() => [...new Set(chartDays.value.flatMap((day) => day.segments.map((item) => item.toolId)))])
const warnings = computed(() => data.value?.warnings ?? [])
const totalCostLabel = computed(() => {
  const totals = data.value?.totals
  if (!totals) {
    return '—'
  }
  if (totals.calls > 0 && totals.unknown_price_calls >= totals.calls) {
    return '未知'
  }
  return formatCost(totals.estimated_cost)
})

function toolName(toolId: string): string {
  return tools.value.find((tool) => tool.id === toolId)?.display_name ?? toolId
}

function barHeight(calls: number): string {
  return (calls / maxCalls.value) * 100 + '%'
}

function segmentClass(toolId: string): string {
  const index = chartToolIds.value.indexOf(toolId)
  return 'usage-chart__segment usage-chart__segment--' + (index % 4)
}

onMounted(() => {
  void toolsStore.fetchTools()
  void usage.load(7)
})

function selectRange(value: number): void {
  if (value !== days.value || !loaded.value) {
    void usage.load(value)
  }
}
</script>

<template>
  <div class="usage-page">
    <header class="page-header">
      <div>
        <h1>用量</h1>
        <p>调用次数、Token 与估算花费</p>
      </div>
      <span class="page-header__meta">仅展示 · 不扣费</span>
    </header>

    <div class="usage-page__body">
      <div class="usage-range">
        <span>时间范围</span>
        <div class="usage-range__group" aria-label="时间范围">
          <button
            v-for="range in ranges"
            :key="range"
            class="usage-range__button"
            :class="{ 'usage-range__button--active': days === range }"
            type="button"
            @click="selectRange(range)"
          >
            近 {{ range }} 天
          </button>
        </div>
        <span class="usage-range__spacer"></span>
        <span class="usage-range__hint">数据来源：本机会话日志</span>
      </div>

      <div v-if="loading && !loaded" class="usage-state" role="status">正在汇总用量…</div>
      <div v-else-if="error" class="usage-state usage-state--danger" role="alert">
        <strong>用量读取失败</strong>
        <span>{{ error }}</span>
        <button class="button button--secondary" type="button" @click="selectRange(days)">重试</button>
      </div>
      <template v-else-if="data">
        <section class="usage-cards" aria-label="用量汇总">
          <article class="usage-card"><span>调用次数</span><strong>{{ formatInteger(data.totals.calls) }}</strong><small>近 {{ data.days }} 天</small></article>
          <article class="usage-card"><span>输入 Token</span><strong>{{ formatInteger(data.totals.input_tokens) }}</strong><small>{{ formatTokens(data.totals.input_tokens) }}</small></article>
          <article class="usage-card"><span>输出 Token</span><strong>{{ formatInteger(data.totals.output_tokens) }}</strong><small>{{ formatTokens(data.totals.output_tokens) }}</small></article>
          <article class="usage-card" :class="{ 'usage-card--warning': data.totals.unknown_price_calls > 0 }">
            <span>估算花费</span><strong>{{ totalCostLabel }}</strong>
            <small>{{ data.totals.unknown_price_calls > 0 ? data.totals.unknown_price_calls + ' 次价格未知' : '价格已知' }}</small>
          </article>
        </section>

        <div v-if="warnings.length > 0" class="usage-warnings" role="status">
          <p v-for="warning in warnings" :key="warning.code + warning.message">{{ warning.message }}</p>
        </div>

        <section class="usage-chart-card" aria-label="每日调用">
          <header class="usage-card-head">
            <div><h2>每日调用</h2><p>按工具拆分 · 最近 {{ Math.min(chartDays.length, 14) }} 天</p></div>
            <div class="usage-chart__legend">
              <span v-for="(toolId, index) in chartToolIds" :key="toolId">
                <i :class="'usage-chart__legend-dot usage-chart__legend-dot--' + (index % 4)"></i>{{ toolName(toolId) }}
              </span>
            </div>
          </header>
          <div v-if="chartDays.length === 0" class="usage-chart__empty">当前范围没有可展示的调用记录。</div>
          <div v-else class="usage-chart" role="img" aria-label="每日调用柱状图">
            <div v-for="day in chartDays" :key="day.date" class="usage-chart__column">
              <span class="usage-chart__value">{{ day.calls }}</span>
              <div class="usage-chart__bar">
                <span
                  v-for="segment in day.segments"
                  :key="segment.toolId"
                  :class="segmentClass(segment.toolId)"
                  :style="{ height: barHeight(segment.calls) }"
                  :title="toolName(segment.toolId) + ' ' + segment.calls + ' 次'"
                ></span>
              </div>
              <span class="usage-chart__date">{{ formatDate(day.date) }}</span>
            </div>
          </div>
        </section>

        <div class="usage-notice">
          <strong>估算口径</strong>
          <span>费用按内置价格表 × Token 估算，仅展示、不扣费；未知价格显示「未知」，且不计入合计。</span>
          <span>{{ data.pricing_note }}</span>
        </div>

        <section class="usage-table-card" aria-label="用量明细">
          <header class="usage-card-head">
            <div><h2>用量明细</h2><p>共 {{ data.records.length }} 组记录</p></div>
            <span class="usage-table-card__meta">{{ totalCostLabel === '未知' ? '未知价格未计入' : totalCostLabel + ' 已估算' }}</span>
          </header>
          <div v-if="data.records.length === 0" class="usage-table__empty">当前范围没有用量记录。</div>
          <div v-else class="usage-table">
            <div class="usage-table__head">
              <span>日期</span><span>工具</span><span>模型</span><span>调用</span><span>输入</span><span>输出</span><span>花费</span>
            </div>
            <div v-for="record in data.records" :key="record.date + record.tool_id + (record.model ?? '')" class="usage-table__row">
              <span>{{ record.date }}</span>
              <strong>{{ toolName(record.tool_id) }}</strong>
              <code>{{ record.model ?? '未知模型' }}</code>
              <span>{{ formatInteger(record.calls) }}</span>
              <span>{{ formatInteger(record.input_tokens) }}</span>
              <span>{{ formatInteger(record.output_tokens) }}</span>
              <span :class="{ 'usage-table__unknown': !record.price_known }">{{ formatCost(record.estimated_cost, record.price_known) }}</span>
            </div>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>

<style scoped>
.usage-page { display: flex; flex-direction: column; height: 100%; min-height: 0; background: var(--color-bg); }
.page-header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-lg); min-height: 65px; padding: var(--space-md) var(--space-xl); border-bottom: 1px solid var(--color-border); background: var(--color-surface); }
.page-header h1 { margin: 0; font-size: var(--font-size-xl); line-height: var(--line-height-tight); }
.page-header p { margin: 2px 0 0; color: var(--color-text-secondary); font-size: var(--font-size-xs); }
.page-header__meta { padding: 3px 8px; border-radius: 999px; background: var(--color-success-bg); color: var(--color-success-fg); font-size: var(--font-size-xs); font-weight: 600; }
.usage-page__body { display: flex; flex: 1; flex-direction: column; gap: var(--space-md); min-height: 0; padding: var(--space-xl); overflow-y: auto; }
.usage-range { display: flex; align-items: center; gap: var(--space-md); padding: var(--space-sm) var(--space-md); border: 1px solid var(--color-border-card); border-radius: var(--radius-lg); background: var(--color-surface); color: var(--color-text-secondary); font-size: var(--font-size-xs); }
.usage-range__group { display: flex; padding: 2px; border-radius: var(--radius-md); background: var(--color-bg-subtle); }
.usage-range__button { padding: 4px 10px; border: 1px solid transparent; border-radius: var(--radius-sm); background: transparent; color: var(--color-text-secondary); font-size: var(--font-size-xs); cursor: pointer; }
.usage-range__button--active { border-color: var(--color-border-control); background: var(--color-surface); color: var(--color-text); font-weight: 600; }
.usage-range__spacer { flex: 1; }
.usage-range__hint { color: var(--color-text-muted); }
.usage-state { display: flex; flex: 1; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-sm); color: var(--color-text-secondary); font-size: var(--font-size-sm); }
.usage-state--danger { color: var(--color-danger-fg); }
.usage-cards { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-md); }
.usage-card { display: flex; flex-direction: column; gap: 2px; padding: var(--space-lg); border: 1px solid var(--color-border-card); border-radius: var(--radius-lg); background: var(--color-surface); }
.usage-card span { color: var(--color-text-secondary); font-size: var(--font-size-xs); font-weight: 600; }
.usage-card strong { font-size: 23px; line-height: 1.3; }
.usage-card small { color: var(--color-text-muted); font-size: 10px; }
.usage-card--warning small { color: var(--color-warning-fg); }
.usage-warnings { padding: var(--space-sm) var(--space-md); border-radius: var(--radius-md); background: var(--color-warning-bg); color: var(--color-warning-fg); font-size: var(--font-size-xs); }
.usage-warnings p { margin: 0; }
.usage-chart-card, .usage-table-card { border: 1px solid var(--color-border-card); border-radius: var(--radius-lg); background: var(--color-surface); }
.usage-card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-lg); padding: var(--space-md) var(--space-lg) 0; }
.usage-card-head h2 { margin: 0; font-size: var(--font-size-md); }
.usage-card-head p { margin: 2px 0 0; color: var(--color-text-secondary); font-size: var(--font-size-xs); }
.usage-chart__legend { display: flex; flex-wrap: wrap; gap: var(--space-md); color: var(--color-text-secondary); font-size: var(--font-size-xs); }
.usage-chart__legend span { display: inline-flex; align-items: center; gap: var(--space-xs); }
.usage-chart__legend-dot { width: 8px; height: 8px; border-radius: 2px; }
.usage-chart__legend-dot--0, .usage-chart__segment--0 { background: var(--color-primary); }
.usage-chart__legend-dot--1, .usage-chart__segment--1 { background: var(--color-accent); }
.usage-chart__legend-dot--2, .usage-chart__segment--2 { background: var(--color-success); }
.usage-chart__legend-dot--3, .usage-chart__segment--3 { background: var(--color-warning); }
.usage-chart { display: flex; align-items: flex-end; gap: var(--space-lg); height: 180px; padding: var(--space-lg) var(--space-xl) var(--space-md); overflow-x: auto; }
.usage-chart__column { display: flex; flex: 1; flex-direction: column; align-items: center; justify-content: flex-end; gap: var(--space-xs); min-width: 34px; height: 100%; }
.usage-chart__value { color: var(--color-text-muted); font-size: 10px; }
.usage-chart__bar { display: flex; flex-direction: column-reverse; justify-content: flex-start; width: 28px; height: 120px; overflow: hidden; border-radius: 3px; background: var(--color-bg-subtle); }
.usage-chart__segment { display: block; width: 100%; min-height: 2px; }
.usage-chart__date { color: var(--color-text-muted); font-size: 10px; white-space: nowrap; }
.usage-chart__empty, .usage-table__empty { padding: var(--space-2xl); color: var(--color-text-muted); font-size: var(--font-size-sm); text-align: center; }
.usage-notice { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-sm) var(--space-md); padding: var(--space-sm) var(--space-md); border-radius: var(--radius-md); background: var(--color-warning-bg); color: var(--color-warning-fg); font-size: var(--font-size-xs); }
.usage-notice span:last-child { color: var(--color-text-secondary); }
.usage-table-card__meta { color: var(--color-text-muted); font-size: var(--font-size-xs); }
.usage-table { overflow-x: auto; padding: 0 var(--space-lg) var(--space-md); }
.usage-table__head, .usage-table__row { display: grid; grid-template-columns: 90px 120px minmax(180px, 1fr) 70px 95px 95px 100px; gap: var(--space-sm); align-items: center; min-width: 760px; padding: var(--space-sm) var(--space-sm); font-size: var(--font-size-xs); }
.usage-table__head { border-bottom: 1px solid var(--color-border); color: var(--color-text-secondary); font-weight: 600; }
.usage-table__row { border-bottom: 1px solid var(--color-bg-subtle); color: var(--color-info-fg); }
.usage-table__row strong { color: var(--color-text); }
.usage-table__row code { font-family: var(--font-mono); overflow-wrap: anywhere; }
.usage-table__unknown { color: var(--color-warning-fg); font-weight: 600; }
@media (max-width: 980px) { .usage-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .usage-page__body { padding: var(--space-lg); } .usage-range { flex-wrap: wrap; } .usage-cards { grid-template-columns: 1fr; } }
</style>
