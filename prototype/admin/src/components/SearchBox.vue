<script setup>
// The search field at the top of a table page. v-model is what's typed.
defineProps({ placeholder: { type: String, required: true } })
const query = defineModel({ type: String, default: '' })
</script>

<template>
  <label class="search">
    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4 4" /></svg>
    <input v-model="query" type="search" :placeholder="placeholder" :aria-label="placeholder" />
  </label>
</template>
