<script setup>
// Every partner hospital's doctors, with their timetable and consultation fee.
// Click a fee to change it, as on Prices.
import { computed, ref } from 'vue'
import { api } from '../api'
import AmountCell from '../components/AmountCell.vue'
import AsyncContent from '../components/AsyncContent.vue'
import SearchBox from '../components/SearchBox.vue'

const doctors = ref([])
const specialties = ref([])
const query = ref('')
const specialty = ref('') // a specialty id, or '' for all
const note = ref('Point at a fee, or tab to it, to see where it came from and when.')

async function load() {
  ;[doctors.value, specialties.value] = await Promise.all([api.doctors(), api.specialties()])
}

const hospitalCount = computed(() => new Set(doctors.value.map((d) => d.hospital_id)).size)

// Grouped by hospital in name order, as on Prices. The API's "nearest first"
// means nothing here: an admin has no location.
const visible = computed(() => {
  const q = query.value.trim().toLowerCase()
  return doctors.value
    .filter((d) => !specialty.value || d.specialty === specialty.value)
    .filter((d) => `${d.name} ${d.specialty_name} ${d.hospital.name} ${d.hospital.area}`.toLowerCase().includes(q))
    .sort((a, b) => a.hospital.name.localeCompare(b.hospital.name))
})

async function saveFee(doctor, fee) {
  doctor.fee = (await api.updateFee(doctor.id, fee)).fee
}
</script>

<template>
  <div class="page-head">
    <div>
      <h1>Doctors</h1>
      <p class="lede">
        {{ doctors.length }} doctors at {{ hospitalCount }} partner hospitals. Click a fee to change it.
      </p>
    </div>
    <SearchBox v-model="query" placeholder="Find a doctor, specialty or hospital" />
  </div>

  <AsyncContent :load="load">
    <div class="card sheet">
      <div class="sheet-head">
        <label class="field">
          <span class="sr-only">Specialty</span>
          <select v-model="specialty">
            <option value="">All specialties</option>
            <option v-for="s in specialties" :key="s.id" :value="s.id">{{ s.name }} ({{ s.doctor_count }})</option>
          </select>
        </label>
        <div class="legend"><span class="key changed">Changed today</span></div>
      </div>

      <div class="table-wrap">
        <table class="rows doctors">
          <thead>
            <tr>
              <th scope="col">Doctor</th>
              <th scope="col">Specialty</th>
              <th scope="col">Hospital</th>
              <th scope="col">Days</th>
              <th scope="col">Sessions</th>
              <th scope="col" class="right">Fee</th>
            </tr>
          </thead>

          <tbody>
            <tr v-for="doctor in visible" :key="doctor.id">
              <th scope="row">
                <div class="h-name">{{ doctor.name }} <span class="demo-badge">Demo</span></div>
                <div class="h-meta">{{ doctor.qualifications }}</div>
              </th>
              <td>{{ doctor.specialty_name }}</td>
              <td>
                <div class="hospital">
                  <span class="swatch" :style="{ background: doctor.hospital.brand_color }" aria-hidden="true"></span>
                  <div>
                    <div>{{ doctor.hospital.name }}</div>
                    <div class="h-meta">{{ doctor.hospital.area }}</div>
                  </div>
                </div>
              </td>
              <td>{{ doctor.days.join(', ') }}</td>
              <td>{{ Object.keys(doctor.slots).join(', ') }}</td>
              <td class="right">
                <AmountCell
                  :price="doctor.fee"
                  :label="`${doctor.name}'s fee`"
                  :commit="(fee) => saveFee(doctor, fee)"
                  @show="note = $event"
                />
              </td>
            </tr>
            <tr v-if="!visible.length">
              <td colspan="6" class="empty">No doctor matches that search.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <p class="caption">{{ note }}</p>
  </AsyncContent>
</template>
