// The en-IN locale groups digits the Indian way: ₹1,450 and ₹1,25,000.
const inr = new Intl.NumberFormat('en-IN')

export const rupees = (amount) => `₹${inr.format(amount)}`

/** "1 price", "3 prices". */
export const plural = (count, word) => `${count} ${word}${count === 1 ? '' : 's'}`

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2026-09-12" -> "12 Sep 2026", the same in every browser and in the app. */
export const longDate = (isoDate) => {
  const [year, month, day] = isoDate.split('-').map(Number)
  return `${day} ${MONTHS[month - 1]} ${year}`
}

/** Where a price came from and when: "Price list submitted by the hospital · 12 Sept 2026". */
export const provenance = (price) => `${price.source} · ${longDate(price.as_of)}`

// India has one time zone and no daylight saving, so a fixed offset is exact.
const IST_OFFSET_MS = 330 * 60 * 1000

/** Today in Bengaluru as "2026-09-28": the date the API stamps on each edit. */
export const today = () => new Date(Date.now() + IST_OFFSET_MS).toISOString().slice(0, 10)
