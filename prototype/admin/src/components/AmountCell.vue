<script setup>
// One rupee amount, edited in place like a spreadsheet cell: click it, type,
// then Enter or click away to save, or Esc to cancel. Enter and Esc hand focus
// back to the cell; Enter's default is prevented, or its keypress would click
// the refocused cell and open it again. Prices and Doctors both use it.
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import { provenance, rupees, today } from '../format'
import { toast } from '../toast'

defineOptions({ inheritAttrs: false }) // a page's extra classes go on the button
const props = defineProps({
  price: { type: Object, default: null }, // { amount, source, as_of }, or null: none yet
  label: { type: String, required: true }, // what the amount is for: "Dr. Ananya Rao's fee"
  commit: { type: Function, required: true }, // async (amount): saves it, updates the page
})
const emit = defineEmits(['show']) // pointed at or focused: where the amount came from

const editing = ref(false)
const draft = ref('')
const saved = ref(false) // flashes the cell for a moment after a save
const input = ref(null)
const button = ref(null)

const about = computed(() =>
  props.price
    ? `${props.label}, ${rupees(props.price.amount)}: ${provenance(props.price)}`
    : `${props.label}: no price yet`,
)

let before // the amount when the cell was opened
async function open() {
  before = props.price?.amount
  draft.value = before ?? ''
  editing.value = true
  await nextTick()
  input.value.select()
}

async function close(refocus) {
  editing.value = false
  if (!refocus) return
  await nextTick()
  button.value.focus()
}

async function save(refocus) {
  if (!editing.value) return // Enter and Esc remove the input, which fires blur too
  close(refocus)
  const text = String(draft.value).replace(/[₹,\s]/g, '')
  const amount = Number(text)
  if (text === '' || amount === before) return
  if (!Number.isInteger(amount) || amount < 1 || amount > 100000) {
    return toast('Enter a whole number of rupees, from 1 to 1,00,000.')
  }
  try {
    await props.commit(amount)
    toast(`Saved: ${props.label} is now ${rupees(amount)}.`)
    flash()
    // Enter refocused the cell before the new amount arrived; describe the new one.
    if (refocus) nextTick(() => emit('show', about.value))
  } catch (error) {
    toast(error.message)
  }
}

let flashTimer
function flash() {
  saved.value = true
  clearTimeout(flashTimer)
  flashTimer = setTimeout(() => (saved.value = false), 1600) // the animation's length
}
onBeforeUnmount(() => clearTimeout(flashTimer))
</script>

<template>
  <input
    v-if="editing"
    ref="input"
    v-model="draft"
    class="cell-input"
    inputmode="numeric"
    :aria-label="label"
    @keydown.enter.prevent="save(true)"
    @keydown.esc="close(true)"
    @blur="save(false)"
  />
  <button
    v-else
    ref="button"
    v-bind="$attrs"
    type="button"
    class="cell"
    :class="{ missing: !price, 'changed-today': price?.as_of === today(), saved }"
    :title="about"
    @click="open"
    @mouseenter="emit('show', about)"
    @focus="emit('show', about)"
  >
    {{ price ? rupees(price.amount) : 'Add' }}
  </button>
</template>
