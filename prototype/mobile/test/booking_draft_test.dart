import 'package:flutter_test/flutter_test.dart';
import 'package:ratecard/booking_draft.dart';
import 'package:ratecard/format.dart';
import 'package:ratecard/location.dart';

void main() {
  /// A draft opened at [hour]:[minute] on Tuesday 29 September 2026.
  BookingDraft openedAt(int hour, [int minute = 0]) =>
      BookingDraft(now: () => DateTime(2026, 9, 29, hour, minute));

  test('early in the day, every slot today is open', () {
    final draft = openedAt(6);
    expect(draft.day, DateTime(2026, 9, 29));
    expect(draft.period, 'Morning');
    expect(draft.openSlots(draft.day, 'Morning').first, '07:00');
  });

  test('a slot closes half an hour before it starts', () {
    final draft = openedAt(8, 10);
    expect(draft.openSlots(draft.day, 'Morning'), ['09:00', '10:00', '11:00']);
  });

  test('once the morning has gone, the afternoon is picked', () {
    expect(openedAt(11, 45).period, 'Afternoon');
  });

  test('late at night, today is closed and tomorrow is picked', () {
    final draft = openedAt(22);
    expect(draft.isOpen(draft.days.first), isFalse);
    expect(draft.day, DateTime(2026, 9, 30));
  });

  test('slots follow India’s clock: 8 PM UTC is 1:30 AM the next day there', () {
    expect(istAt(DateTime.utc(2026, 9, 29, 20)), DateTime(2026, 9, 30, 1, 30));
  });

  test('the week runs across the end of the month', () {
    expect(openedAt(6).days.last, DateTime(2026, 10, 5));
  });

  test('changing the day or the period clears the chosen time', () {
    final draft = openedAt(6)..pickTime('08:00');
    draft.pickDay(draft.days[2]);
    expect(draft.time, isNull);

    draft
      ..pickTime('08:00')
      ..pickPeriod('Evening');
    expect(draft.time, isNull);
  });

  test('clearTime stops the same slot being booked twice', () {
    final draft = openedAt(6)..pickTime('08:00');
    draft.clearTime();
    expect(draft.time, isNull);
  });

  group('a doctor in on Mondays, Wednesdays and Fridays', () {
    /// A draft for their mornings and evenings, opened at [hour] on [day] of
    /// September or October 2026.
    BookingDraft doctorDraft({int day = 29, int month = 9, int hour = 9}) => BookingDraft(
      now: () => DateTime(2026, month, day, hour),
      timetable: const {
        'Morning': ['09:00', '09:30'],
        'Evening': ['17:00', '17:30'],
      },
      weekdays: const {DateTime.monday, DateTime.wednesday, DateTime.friday},
    );

    test('opened on a Tuesday, starts on Wednesday', () {
      final draft = doctorDraft();
      expect(draft.day, DateTime(2026, 9, 30));
      expect(draft.period, 'Morning');
    });

    test('only their days are open', () {
      final draft = doctorDraft();
      final open = [
        for (final day in draft.days)
          if (draft.isOpen(day)) weekday(day),
      ];
      expect(open, ['Wed', 'Fri', 'Mon']);
    });

    test('only their sessions are offered', () {
      final draft = doctorDraft();
      expect(draft.timetable.keys, ['Morning', 'Evening']);
      expect(draft.openSlots(draft.day), ['09:00', '09:30', '17:00', '17:30']);
    });

    test('after Friday evening, the next open day is Monday', () {
      expect(doctorDraft(day: 2, month: 10, hour: 20).day, DateTime(2026, 10, 5));
    });
  });
}
