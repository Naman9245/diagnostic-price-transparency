// The dashboard's one toast: the latest message, shown for a few seconds.
// App.vue renders it; any page or component can call toast().
import { ref } from 'vue'

export const toastMessage = ref('')
let timer

export function toast(message) {
  toastMessage.value = message
  clearTimeout(timer)
  timer = setTimeout(() => (toastMessage.value = ''), 3500)
}
