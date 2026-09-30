<script setup>
// A strip from the cheapest price to the priciest, one dot per hospital.
// The same picture as in the mobile app: how far one test's price varies.
import { computed } from 'vue'
import { rupees } from '../format'

const props = defineProps({
  prices: { type: Array, required: true },
})

const WIDTH = 96
const HEIGHT = 14
const PAD = 5

const low = computed(() => Math.min(...props.prices))
const high = computed(() => Math.max(...props.prices))

function x(price) {
  if (high.value === low.value) return WIDTH / 2
  return PAD + ((price - low.value) / (high.value - low.value)) * (WIDTH - 2 * PAD)
}
</script>

<template>
  <svg
    class="spread"
    :width="WIDTH"
    :height="HEIGHT"
    :viewBox="`0 0 ${WIDTH} ${HEIGHT}`"
    role="img"
    :aria-label="`From ${rupees(low)} to ${rupees(high)}`"
  >
    <!-- A thin rect, not a line: a gradient can't paint a shape with zero height. -->
    <rect
      :x="PAD"
      :y="HEIGHT / 2 - 1.5"
      :width="WIDTH - 2 * PAD"
      height="3"
      rx="1.5"
      fill="url(#spread-track)"
    />
    <circle
      v-for="(price, i) in prices"
      :key="i"
      :cx="x(price)"
      :cy="HEIGHT / 2"
      r="2.8"
      fill="#fff"
      stroke="#1c1c1c"
      stroke-opacity="0.6"
      stroke-width="1.3"
    />
  </svg>
</template>
