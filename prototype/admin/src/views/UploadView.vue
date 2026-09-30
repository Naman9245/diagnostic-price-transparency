<script setup>
// Upload a hospital's rate card, check how each name on it was matched to one
// of our tests, then publish the prices you trust.
//
// The reading is mocked (the API returns the same rows for any file). The name
// matching is real, and it's the part worth looking at: only an exact, known
// name is ticked for you. Anything that merely looks similar waits for a person.
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import { plural, rupees } from '../format'

const hospitals = ref([])
const hospitalId = ref('')
const dragging = ref(false)
const steps = ref([]) // pipeline steps shown while "reading"
const reading = ref(false)
const result = ref(null) // what the API read from the sheet
const selected = ref(new Set()) // line numbers ticked for publishing
const notice = ref('')
const error = ref('')
const publishing = ref(false)
const published = ref(null)

onMounted(async () => {
  try {
    hospitals.value = await api.hospitals()
    hospitalId.value = hospitals.value[0]?.id ?? ''
  } catch (e) {
    error.value = e.message
  }
})

const counts = computed(() => {
  const rows = result.value?.rows ?? []
  const count = (match) => rows.filter((r) => r.match === match).length
  return { exact: count('exact'), review: count('review'), none: count('none') }
})

const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, reduceMotion ? 0 : ms))

/** Forgets the last sheet: before a new upload, or when the hospital changes. */
function clearResult() {
  error.value = ''
  notice.value = ''
  published.value = null
  result.value = null
  steps.value = []
}

// A sheet belongs to the hospital it was read for, so switching hospital drops it.
watch(hospitalId, clearResult)

async function upload(file) {
  if (!hospitalId.value || reading.value) return
  clearResult()
  reading.value = true
  try {
    const request = api.extractSheet(hospitalId.value, file)
    request.catch(() => {}) // handled below; this stops an "unhandled" warning meanwhile
    // The API answers at once. Showing the stages one by one explains what a
    // real reader does with a rate card.
    for (const step of ['Reading the document', 'Finding test names and prices', 'Matching names to our tests']) {
      steps.value.push(step)
      await pause(450)
    }
    result.value = await request
    selected.value = new Set(result.value.rows.filter((r) => r.match === 'exact').map((r) => r.line))
  } catch (e) {
    error.value = e.message
    steps.value = []
  } finally {
    reading.value = false
  }
}

function onDrop(event) {
  dragging.value = false
  const file = event.dataTransfer.files[0]
  if (file) upload(file)
}

function onDragLeave(event) {
  // dragleave also fires when moving onto the zone's own text; ignore those.
  if (!event.currentTarget.contains(event.relatedTarget)) dragging.value = false
}

function onPick(event) {
  const file = event.target.files[0]
  if (file) upload(file)
  event.target.value = '' // lets the same file be picked again
}

async function useSample() {
  try {
    const response = await fetch('/sample-rate-card.csv')
    if (!response.ok) throw new Error(response.statusText)
    upload(new File([await response.blob()], 'sample-rate-card.csv', { type: 'text/csv' }))
  } catch {
    error.value = "Couldn't load the sample sheet. Reload the page and try again."
  }
}

function toggle(row, event) {
  notice.value = ''
  const next = new Set(selected.value)
  if (next.has(row.line)) {
    next.delete(row.line)
  } else {
    // Two rows can't both set the same test's price.
    const clash = result.value.rows.find((r) => next.has(r.line) && r.test_id === row.test_id)
    if (clash) {
      notice.value = `Line ${clash.line} already sets the price of ${row.test_name}. Untick it first.`
      event.target.checked = false // the click already ticked the box; undo that
      return
    }
    next.add(row.line)
  }
  selected.value = next
}

const matchLabel = (row) =>
  ({
    exact: 'Exact name',
    review: `Looks like · ${Math.round(row.similarity * 100)}%`,
    none: 'Not a test we list',
  })[row.match]

async function publish() {
  const rows = result.value.rows.filter((r) => selected.value.has(r.line))
  const prices = Object.fromEntries(rows.map((r) => [r.test_id, r.price]))
  // The API keeps a source to 120 characters, so a very long file name is cut short.
  const full = `Price sheet: ${result.value.file_name}`
  const source = full.length > 120 ? `${full.slice(0, 119)}…` : full
  publishing.value = true
  error.value = ''
  try {
    await api.updatePrices(result.value.hospital_id, prices, source)
    published.value = { count: rows.length, hospital: result.value.hospital_name, source }
    result.value = null
    steps.value = []
  } catch (e) {
    error.value = e.message
  } finally {
    publishing.value = false
  }
}
</script>

<template>
  <div class="page-head">
    <div>
      <h1>Upload price sheet</h1>
      <p class="lede">
        Drop a hospital's rate card. Each test name and price on it is read, then matched to one of our tests.
      </p>
    </div>
  </div>

  <div class="upload-grid">
    <label class="field">
      <span>Hospital</span>
      <select v-model="hospitalId" :disabled="reading">
        <option v-for="h in hospitals" :key="h.id" :value="h.id">{{ h.name }}</option>
      </select>
    </label>

    <div
      class="dropzone"
      :class="{ dragging }"
      @dragover.prevent="dragging = true"
      @dragleave="onDragLeave"
      @drop.prevent="onDrop"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4m0 0-5 5m5-5 5 5M5 20h14" /></svg>
      <p class="drop-title">Drop a PDF, Excel sheet, CSV or photo here</p>
      <p class="muted">
        or
        <label class="link">choose a file<input type="file" hidden accept=".pdf,.xlsx,.xls,.csv,.jpg,.jpeg,.png" :disabled="reading || !hospitalId" @change="onPick" /></label>
        · up to 10 MB ·
        <button type="button" class="link" :disabled="reading || !hospitalId" @click="useSample">try a sample sheet</button>
      </p>
    </div>
  </div>

  <p v-if="error" class="card error-box">{{ error }}</p>

  <ol v-if="steps.length" class="steps" aria-live="polite">
    <li v-for="(step, i) in steps" :key="step" :class="{ done: !reading || i < steps.length - 1 }">{{ step }}</li>
  </ol>

  <section v-if="result" class="card sheet">
    <header class="sheet-head">
      <div>
        <h2>{{ result.file_name }}</h2>
        <p class="muted">
          {{ plural(result.rows.length, 'row') }} read for {{ result.hospital_name }}
          <span class="demo-badge">Demo</span>
        </p>
      </div>
      <div class="tallies">
        <span class="match-pill exact">{{ counts.exact }} exact</span>
        <span class="match-pill review">{{ counts.review }} to check</span>
        <span class="match-pill none">{{ counts.none }} not tests we list</span>
      </div>
    </header>

    <div class="table-wrap">
      <table class="rows">
        <thead>
          <tr>
            <th scope="col"><span class="sr-only">Publish</span></th>
            <th scope="col">Line</th>
            <th scope="col">As printed on the sheet</th>
            <th scope="col" class="right">Price</th>
            <th scope="col">Our test</th>
            <th scope="col" class="right">Now</th>
            <th scope="col">Match</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in result.rows" :key="row.line" :class="[row.match, { chosen: selected.has(row.line) }]">
            <td>
              <input
                type="checkbox"
                :checked="selected.has(row.line)"
                :disabled="row.match === 'none'"
                :aria-label="`Publish line ${row.line}, ${row.raw_name}`"
                @change="toggle(row, $event)"
              />
            </td>
            <td class="muted num">{{ row.line }}</td>
            <td class="raw">{{ row.raw_name }}</td>
            <td class="right num strong">{{ rupees(row.price) }}</td>
            <td>{{ row.test_name ?? '—' }}</td>
            <td class="right num muted">{{ row.current_price ? rupees(row.current_price) : '—' }}</td>
            <td><span class="match-pill" :class="row.match">{{ matchLabel(row) }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>

    <footer class="sheet-foot">
      <p class="muted">
        Exact names are ticked for you. Tick a “looks like” row only once you've checked it's the same
        test, because a similar name isn't always the same test.
      </p>
      <p v-if="notice" class="notice">{{ notice }}</p>
      <button type="button" class="btn btn-primary" :disabled="!selected.size || publishing" @click="publish">
        Publish {{ plural(selected.size, 'price') }}
      </button>
    </footer>
  </section>

  <div v-if="published" class="card success" role="status">
    <strong>
      Published {{ plural(published.count, 'price') }} for {{ published.hospital }}
      <span class="demo-badge">Demo</span>.
    </strong>
    Each one now shows “{{ published.source }}” as its source, dated today.
    <RouterLink to="/prices">See them in Prices</RouterLink>
  </div>
</template>
