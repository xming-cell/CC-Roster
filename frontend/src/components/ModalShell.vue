<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps<{
  labelledBy: string
  role?: 'dialog' | 'alertdialog'
  size?: 'default' | 'wide'
}>()

const emit = defineEmits<{
  close: []
}>()

const dialog = ref<HTMLElement | null>(null)
let previousFocus: HTMLElement | null = null

function focusableElements(): HTMLElement[] {
  const root = dialog.value
  if (root === null) {
    return []
  }
  return Array.from(
    root.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  )
}

function requestClose(): void {
  emit('close')
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.preventDefault()
    requestClose()
    return
  }
  if (event.key !== 'Tab') {
    return
  }
  const focusable = focusableElements()
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (first === undefined || last === undefined) {
    event.preventDefault()
    return
  }
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

onMounted(async () => {
  previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  await nextTick()
  const focusable = focusableElements()
  ;(focusable[0] ?? dialog.value)?.focus()
  window.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
  if (previousFocus?.isConnected === true) {
    previousFocus.focus()
  }
})
</script>

<template>
  <div class="modal-backdrop" @mousedown.self="requestClose">
    <div
      ref="dialog"
      class="modal"
      :class="{ 'modal--wide': props.size === 'wide' }"
      :role="props.role ?? 'dialog'"
      aria-modal="true"
      :aria-labelledby="props.labelledBy"
      tabindex="-1"
    >
      <slot />
    </div>
  </div>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-xl);
  background: color-mix(in srgb, var(--color-text) 42%, transparent);
}

.modal {
  width: min(560px, 100%);
  max-height: calc(100vh - 48px);
  overflow-y: auto;
  border: 1px solid var(--color-border-card);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  box-shadow: var(--shadow-card);
}

.modal--wide {
  width: min(640px, 100%);
}

@media (max-width: 720px) {
  .modal-backdrop {
    align-items: flex-end;
    padding: var(--space-md);
  }

  .modal {
    max-height: calc(100vh - 24px);
  }
}
</style>


