<script setup>
// The frame around every page: sidebar navigation, the demo notice and the toast.
import { toastMessage } from './toast'
</script>

<template>
  <!-- Shared by every price-spread strip on the page. -->
  <svg width="0" height="0" aria-hidden="true" style="position: absolute">
    <defs>
      <linearGradient id="spread-track" x1="0" x2="1" y1="0" y2="0">
        <stop offset="0" stop-color="#347a71" />
        <stop offset="0.5" stop-color="#e3a21a" />
        <stop offset="1" stop-color="#c4453c" />
      </linearGradient>
    </defs>
  </svg>

  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true">₹</span>
        <span>RateCard <small>Admin</small></span>
      </div>
      <nav class="nav" aria-label="Main">
        <RouterLink to="/prices">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v14H4zM4 10h16M10 5v14" /></svg>
          Prices
        </RouterLink>
        <RouterLink to="/doctors">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3h4m4 0h4M5 3v6a4 4 0 0 0 8 0V3M9 13v2a5 5 0 0 0 10 0v-3" /><circle cx="19" cy="10" r="2" /></svg>
          Doctors
        </RouterLink>
        <RouterLink to="/upload">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4m0 0-5 5m5-5 5 5M5 20h14" /></svg>
          Upload price sheet
        </RouterLink>
      </nav>
      <p class="sidebar-note">
        <span class="demo-badge">Demo</span>
        Every hospital, doctor and price is made up. Changes last until the API restarts.
      </p>
    </aside>

    <main>
      <RouterView />
    </main>
  </div>

  <!-- Always on the page, so screen readers announce each message that appears in it. -->
  <div role="status">
    <Transition name="toast">
      <div v-if="toastMessage" class="toast">{{ toastMessage }}</div>
    </Transition>
  </div>
</template>
