<script setup>
// Runs `load` when the page opens: a placeholder while it runs, then the page,
// or the error with a way to try again.
import { onMounted, ref } from 'vue'

const props = defineProps({ load: { type: Function, required: true } })
const loading = ref(true)
const error = ref('')

async function run() {
  loading.value = true
  error.value = ''
  try {
    await props.load()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
onMounted(run)
</script>

<template>
  <div v-if="error" class="card error-box">
    <p>{{ error }}</p>
    <button type="button" class="btn btn-ghost" @click="run">Try again</button>
  </div>
  <div v-else-if="loading" class="card skeleton" style="height: 480px"></div>
  <slot v-else />
</template>
