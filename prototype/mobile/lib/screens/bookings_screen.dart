import 'package:flutter/material.dart';

import '../api.dart';
import '../format.dart';
import '../location.dart';
import '../models.dart';
import '../session.dart';
import '../theme.dart';
import '../widgets/async_view.dart';
import '../widgets/common.dart';
import '../widgets/initials_avatar.dart';
import '../widgets/tree_avatar.dart';

/// The Bookings tab: your tests and doctor's appointments grouped by day,
/// like a booking app's appointments screen. Bookings belong to an account,
/// so signed out it asks you to sign in.
class BookingsScreen extends StatelessWidget {
  const BookingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(automaticallyImplyLeading: false, title: const Text('My bookings')),
      body: ValueListenableBuilder(
        valueListenable: currentUser,
        // Keyed by the account, so signing in as someone else loads theirs.
        builder: (context, user, _) => user == null
            ? EmptyState(
                icon: Icons.event_note_outlined,
                title: 'Sign in to see your bookings',
                message: 'Your bookings are kept under your mobile number.',
                action: 'Sign in',
                onAction: () => ensureSignedIn(context),
              )
            : _BookingList(key: ValueKey(user.phone)),
      ),
    );
  }
}

class _BookingList extends StatefulWidget {
  const _BookingList({super.key});

  @override
  State<_BookingList> createState() => _BookingListState();
}

class _BookingListState extends State<_BookingList> with Reloadable<_BookingList, List<Booking>> {
  bool _upcoming = true;

  @override
  Future<List<Booking>> fetch() => Api.bookings();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 4),
          child: SegmentedPills(
            options: const {true: 'Upcoming', false: 'Past'},
            selected: _upcoming,
            onChanged: (value) => setState(() => _upcoming = value),
          ),
        ),
        Expanded(
          child: AsyncView(
            future: future,
            onRetry: reload,
            placeholder: const LoadingRows(count: 3),
            builder: (context, all) => _list(all),
          ),
        ),
      ],
    );
  }

  Widget _list(List<Booking> all) {
    final today = DateUtils.dateOnly(istNow());
    bool isPast(Booking booking) => booking.date.isBefore(today);
    final bookings = all.where((b) => _upcoming ? !isPast(b) : isPast(b)).toList();
    if (bookings.isEmpty) {
      return EmptyState(
        icon: Icons.event_available_outlined,
        title: _upcoming ? 'No bookings yet' : 'No past bookings',
        message: _upcoming
            ? 'Book a test or a doctor at a partner hospital and it shows up here.'
            : 'Bookings move here once their day has passed.',
        action: _upcoming ? 'Find a test' : null,
        onAction: () => Navigator.pushNamed(context, '/tests'),
      );
    }

    // Group by day. The API already sorts them soonest first.
    final byDay = <DateTime, List<Booking>>{};
    for (final booking in bookings) {
      (byDay[booking.date] ??= []).add(booking);
    }
    return RefreshIndicator(
      onRefresh: refresh,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 48),
        children: [
          for (final MapEntry(key: day, value: dayBookings) in byDay.entries) ...[
            Padding(
              padding: const EdgeInsets.only(top: 16, bottom: 4),
              child: Row(
                children: [
                  Expanded(child: Text(_dayName(day, today), style: AppText.section)),
                  Text(longDate(day), style: AppText.muted),
                ],
              ),
            ),
            for (final booking in dayBookings) _BookingRow(booking: booking),
          ],
        ],
      ),
    );
  }

  static String _dayName(DateTime day, DateTime today) => switch (day.difference(today).inDays) {
    0 => 'Today',
    1 => 'Tomorrow',
    _ => shortDate(day),
  };
}

/// A test shows its lab's tree; a doctor, their initials.
class _BookingRow extends StatelessWidget {
  const _BookingRow({required this.booking});

  final Booking booking;

  @override
  Widget build(BuildContext context) {
    final doctor = booking.isDoctor;
    final place = doctor
        ? 'At the hospital'
        : booking.homeCollection
        ? 'At home'
        : 'At the lab';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (doctor)
            InitialsAvatar(name: booking.title, color: booking.brandColor, size: 48)
          else
            TreeAvatar(color: booking.brandColor, size: 48),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(booking.title, style: AppText.title),
                const SizedBox(height: 4),
                DemoLine(
                  doctor
                      ? '${booking.subtitle} · ${booking.hospitalName}'
                      : '${booking.hospitalName} · ${booking.hospitalArea}',
                ),
                const SizedBox(height: 8),
                MintPill(
                  icon: Icons.schedule_rounded,
                  text: 'Scheduled · ${clockTime(booking.time)} · $place',
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text(rupees(booking.total), style: AppText.price),
        ],
      ),
    );
  }
}
