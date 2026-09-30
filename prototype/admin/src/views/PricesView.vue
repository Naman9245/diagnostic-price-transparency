<script setup>
// Every hospital's price for every test, in one table. Click a price to change
// it. The change goes straight to the API, which records where the price came
// from and when.
import { computed, ref } from 'vue'
import { api } from '../api'
import AmountCell from '../components/AmountCell.vue'
import AsyncContent from '../components/AsyncContent.vue'
import PriceSpread from '../components/PriceSpread.vue'
import SearchBox from '../components/SearchBox.vue'

const tests = ref([])
const hospitals = ref([])
const query = ref('')
const note = ref('Point at a price, or tab to it, to see where it came from and when.')

async function load() {
  ;[tests.value, hospitals.value] = await Promise.all([api.tests(), api.hospitals()])
}

const visible = computed(() => {
  const q = query.value.trim().toLowerCase()
  return hospitals.value.filter((h) => `${h.name} ${h.area}`.toLowerCase().includes(q))
})

// Each test's prices across every hospital, not just the ones on screen.
const spreads = computed(() =>
  Object.fromEntries(
    tests.value.map((test) => {
      const prices = hospitals.value.map((h) => h.prices[test.id]?.amount).filter(Boolean)
      return [test.id, { prices, low: Math.min(...prices), high: Math.max(...prices) }]
    }),
  ),
)

// The cheapest and the priciest price of each test stand out.
function rank(hospital, test) {
  const amount = hospital.prices[test.id]?.amount
  const { low, high } = spreads.value[test.id]
  return { cheapest: amount === low, priciest: amount === high }
}

async function savePrice(hospital, test, amount) {
  hospital.prices = (await api.updatePrices(hospital.id, { [test.id]: amount })).prices
}
</script>

<template>
  <div class="page-head">
    <div>
      <h1>Prices</h1>
      <p class="lede">
        {{ hospitals.length }} hospitals and {{ tests.length }} tests. Click a price to change it.
      </p>
    </div>
    <SearchBox v-model="query" placeholder="Find a hospital or area" />
  </div>

  <AsyncContent :load="load">
    <div class="card table-wrap">
      <table class="matrix">
        <thead>
          <tr>
            <th scope="col" class="col-hospital">Hospital</th>
            <th scope="col" class="col-partner" title="Partners take bookings in the app">Partner</th>
            <th v-for="test in tests" :key="test.id" scope="col" :title="test.name">
              {{ test.short_name }}
            </th>
          </tr>
        </thead>

        <tbody>
          <tr v-for="hospital in visible" :key="hospital.id">
            <th scope="row" class="col-hospital">
              <div class="hospital">
                <span class="swatch" :style="{ background: hospital.brand_color }" aria-hidden="true"></span>
                <div>
                  <div class="h-name">{{ hospital.name }}</div>
                  <div class="h-meta">
                    <span class="demo-badge">Demo</span>
                    {{ hospital.area }} · ★ {{ hospital.rating.toFixed(1) }}
                  </div>
                </div>
              </div>
            </th>
            <td class="col-partner">
              <span v-if="hospital.partner" class="partner-yes" title="Partner: takes bookings">✓</span>
              <span v-else class="muted" title="Listed only: prices, no bookings">—</span>
            </td>
            <td v-for="test in tests" :key="test.id">
              <AmountCell
                :price="hospital.prices[test.id]"
                :label="`${test.name} at ${hospital.name}`"
                :commit="(amount) => savePrice(hospital, test, amount)"
                :class="rank(hospital, test)"
                @show="note = $event"
              />
            </td>
          </tr>
          <tr v-if="!visible.length">
            <td :colspan="tests.length + 2" class="empty">No hospital or area matches “{{ query }}”.</td>
          </tr>
        </tbody>

        <tfoot>
          <tr>
            <th scope="row" class="col-hospital">
              <div class="h-name">Spread across hospitals</div>
              <div class="legend">
                <span class="key cheapest">Cheapest</span>
                <span class="key priciest">Priciest</span>
                <span class="key changed">Changed today</span>
              </div>
            </th>
            <td class="col-partner"></td>
            <td v-for="test in tests" :key="test.id">
              <PriceSpread :prices="spreads[test.id].prices" />
              <div class="ratio">
                {{ (spreads[test.id].high / spreads[test.id].low).toFixed(1) }}×
              </div>
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
    <p class="caption">{{ note }}</p>
  </AsyncContent>
</template>
