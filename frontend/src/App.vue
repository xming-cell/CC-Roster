<script setup lang="ts">
import { onMounted, ref } from 'vue'

const status = ref('loading...')

onMounted(async () => {
  const res = await fetch('/api/health')
  const data = (await res.json()) as { status: string }
  status.value = data.status
})
</script>

<template>
  <p>backend: {{ status }}</p>
</template>