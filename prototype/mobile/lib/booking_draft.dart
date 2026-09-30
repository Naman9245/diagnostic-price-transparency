import 'package:flutter/foundation.dart';

import 'format.dart';
import 'location.dart';

/// The booking being put together on a lab's or a doctor's page: a day, a
/// time slot and, for a test, where the sample is taken. It only ever offers
/// slots that are still open.
///
/// [now], India's time by default, can be swapped in tests to check what's
/// offered at any hour.
class BookingDraft extends ChangeNotifier {
  BookingDraft({
    DateTime Function()? now,
    this.timetable = labTimetable,
    this.weekdays = const {1, 2, 3, 4, 5, 6, 7},
  }) : _now = now ?? istNow {
    final today = _now();
    days = [for (var i = 0; i < 7; i++) DateTime(today.year, today.month, today.day + i)];
    day = days.firstWhere(isOpen, orElse: () => days.first);
    period = _firstOpenPeriod(day);
  }

  /// When partner labs see patients and collect samples. The demo uses one
  /// timetable for every lab; a real partner would publish its own.
  static const labTimetable = {
    'Morning': ['07:00', '07:30', '08:00', '08:30', '09:00', '10:00', '11:00'],
    'Afternoon': ['12:00', '13:00', '14:00', '15:00'],
    'Evening': ['16:00', '17:00', '18:00', '19:00'],
  };

  /// The time slots in each session: Morning, Afternoon and Evening for a
  /// lab, only the sessions they hold for a doctor.
  final Map<String, List<String>> timetable;

  /// The days of the week it's open, numbered like [DateTime.weekday]
  /// (Monday is 1). Every day unless given.
  final Set<int> weekdays;

  final DateTime Function() _now;

  /// Today and the six days after it.
  late final List<DateTime> days;

  late DateTime day;
  late String period;
  String? time;
  bool atHome = false;

  /// The slots still open on [day], in one [period] or across the whole day.
  /// A slot closes half an hour before it starts.
  List<String> openSlots(DateTime day, [String? period]) {
    if (!weekdays.contains(day.weekday)) return const [];
    final cutoff = _now().add(const Duration(minutes: 30));
    final slots = period == null ? timetable.values.expand((s) => s) : timetable[period]!;
    return [
      for (final slot in slots)
        if (_startOf(day, slot).isAfter(cutoff)) slot,
    ];
  }

  bool isOpen(DateTime day) => openSlots(day).isNotEmpty;

  void pickDay(DateTime value) {
    day = value;
    period = _firstOpenPeriod(value);
    time = null;
    notifyListeners();
  }

  void pickPeriod(String value) {
    period = value;
    time = null;
    notifyListeners();
  }

  void pickTime(String value) {
    time = value;
    notifyListeners();
  }

  void pickAtHome(bool value) {
    atHome = value;
    notifyListeners();
  }

  /// Forgets the chosen time, so a booking that's been made can't be sent a
  /// second time by going back and tapping Book again.
  void clearTime() {
    time = null;
    notifyListeners();
  }

  String _firstOpenPeriod(DateTime day) => timetable.keys.firstWhere(
    (period) => openSlots(day, period).isNotEmpty,
    orElse: () => timetable.keys.first,
  );

  static DateTime _startOf(DateTime day, String slot) {
    final (hour, minute) = parseClock(slot);
    return DateTime(day.year, day.month, day.day, hour, minute);
  }
}
