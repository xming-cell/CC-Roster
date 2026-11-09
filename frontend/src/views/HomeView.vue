<script setup lang="ts">
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'

import { useAppStore } from '../stores/app'

const store = useAppStore()
const { backendStatus, backendError } = storeToRefs(store)

onMounted(() => {
  void store.checkBackend()
})
</script>

<template>
  <section class="home">
    <p>backend: {{ backendStatus }}</p>
    <p v-if="backendError" class="home__error">{{ backendError }}</p>
  </section>
</template>

<style scoped>
.home__error {
  color: #b42318;
}
</style>