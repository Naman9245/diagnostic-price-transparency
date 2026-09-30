// Small formatting helpers. They're written out by hand so the app doesn't
// need the intl package.

/// Whole rupees grouped the Indian way: 1450 -> ₹1,450, 125000 -> ₹1,25,000.
String rupees(int amount) {
  final digits = amount.toString();
  if (digits.length <= 3) return '₹$digits';
  // The last three digits form one group; everything before them goes in
  // pairs (lakhs, crores...).
  var rest = digits.substring(0, digits.length - 3);
  final groups = <String>[];
  while (rest.length > 2) {
    groups.insert(0, rest.substring(rest.length - 2));
    rest = rest.substring(0, rest.length - 2);
  }
  groups.insert(0, rest);
  return '₹${groups.join(',')},${digits.substring(digits.length - 3)}';
}

const _weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const _months = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

/// 2026-09-30 -> "Wed, 30 Sep"
String shortDate(DateTime date) => '${weekday(date)}, ${date.day} ${_months[date.month - 1]}';

/// 2026-09-12 -> "12 Sep 2026"
String longDate(DateTime date) => '${date.day} ${_months[date.month - 1]} ${date.year}';

/// 2026-09-30 -> "Wed"
String weekday(DateTime date) => _weekdays[date.weekday - 1];

/// "Wed" -> 3, numbered like [DateTime.weekday].
int weekdayNumber(String name) => _weekdays.indexOf(name) + 1;

/// 2026-09-30 -> "Sep"
String month(DateTime date) => _months[date.month - 1];

/// "16:30" -> (16, 30)
(int, int) parseClock(String hhmm) {
  final [hour, minute] = hhmm.split(':').map(int.parse).toList();
  return (hour, minute);
}

/// "16:30" -> "4:30 PM"
String clockTime(String hhmm) {
  final (hour, minute) = parseClock(hhmm);
  final hour12 = hour % 12 == 0 ? 12 : hour % 12;
  return '$hour12:${minute.toString().padLeft(2, '0')} ${hour < 12 ? 'AM' : 'PM'}';
}

/// 0.34 -> "0.3 km", 14.1 -> "14 km"
String km(double distance) =>
    distance < 10 ? '${distance.toStringAsFixed(1)} km' : '${distance.round()} km';

/// 2140 -> "2.1K", 980 -> "980"
String compactCount(int count) => count < 1000 ? '$count' : '${(count / 1000).toStringAsFixed(1)}K';

/// "9876543210" -> "+91 98765 43210"
String phoneNumber(String digits) => '+91 ${digits.substring(0, 5)} ${digits.substring(5)}';

/// "Dr. Ananya Rao" -> "AR": the first letters of the first and last names,
/// without the "Dr." in front.
String initials(String name) {
  final words = name
      .trim()
      .replaceFirst(RegExp(r'^dr\.?\s+', caseSensitive: false), '')
      .split(RegExp(r'\s+'));
  return [
    words.first,
    if (words.length > 1) words.last,
  ].where((word) => word.isNotEmpty).map((word) => word[0]).join().toUpperCase();
}
