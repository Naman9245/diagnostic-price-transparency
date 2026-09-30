import 'package:flutter/material.dart';

import '../api.dart';
import '../booking_draft.dart';
import '../format.dart';
import '../models.dart';
import '../session.dart';
import '../theme.dart';
import 'common.dart';
import 'schedule.dart';

/// The booking controls on a partner's page: a day strip, the time slots in
/// each session and, for a test that can be done at home, where the sample
/// is taken. Every choice goes straight into [draft].
class BookingPanel extends StatelessWidget {
  const BookingPanel({super.key, required this.draft, this.homeCollectionFee, this.preparation});

  final BookingDraft draft;

  /// What taking the sample at home costs, or null when it can't be done.
  final int? homeCollectionFee;

  /// What to do beforehand, like fasting. Shown when it asks for something.
  final String? preparation;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: draft,
      builder: (context, _) {
        final slots = draft.openSlots(draft.day, draft.period);
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Expanded(child: Text('Pick a day', style: AppText.section)),
                Text('${month(draft.day)} ${draft.day.year}', style: AppText.muted),
              ],
            ),
            const SizedBox(height: 12),
            DayStrip(
              days: draft.days,
              selected: draft.day,
              onSelect: draft.pickDay,
              isOpen: draft.isOpen,
            ),
            const SizedBox(height: 22),
            const Text('Pick a time', style: AppText.section),
            const SizedBox(height: 12),
            SegmentedPills(
              options: {for (final period in draft.timetable.keys) period: period},
              selected: draft.period,
              onChanged: draft.pickPeriod,
            ),
            const SizedBox(height: 14),
            if (slots.isEmpty)
              Text('No ${draft.period.toLowerCase()} times left on this day.', style: AppText.muted)
            else
              TimeChips(slots: slots, selected: draft.time, onSelect: draft.pickTime),
            if (homeCollectionFee case final fee?) ...[
              const SizedBox(height: 22),
              const Text('Sample collection', style: AppText.section),
              const SizedBox(height: 12),
              SegmentedPills(
                options: {
                  false: 'Visit the lab',
                  true: fee == 0 ? 'At home, free' : 'At home +${rupees(fee)}',
                },
                selected: draft.atHome,
                onChanged: draft.pickAtHome,
              ),
            ],
            if (preparation case final note? when needsPreparation(note)) ...[
              const SizedBox(height: 16),
              PrepNote(note),
            ],
          ],
        );
      },
    );
  }
}

/// The full-width button pinned to the bottom of a booking page, as in the
/// design. Once a time is picked it books: it asks you to sign in first if
/// you haven't, sends [book], then opens the confirmation.
class BookBar extends StatefulWidget {
  const BookBar({
    super.key,
    required this.draft,
    required this.price,
    required this.book,
    this.homeCollectionFee,
  });

  final BookingDraft draft;

  /// The price before any home collection fee.
  final int price;

  /// Added to [price] when the sample is taken at home.
  final int? homeCollectionFee;

  /// Sends the booking described by [draft].
  final Future<Booking> Function() book;

  @override
  State<BookBar> createState() => _BookBarState();
}

class _BookBarState extends State<BookBar> {
  bool _sending = false;

  Future<void> _send() async {
    if (!await ensureSignedIn(context) || !mounted) return;
    setState(() => _sending = true);
    try {
      final booking = await widget.book();
      widget.draft.clearTime(); // going back can't book the same slot twice
      if (mounted) Navigator.pushNamed(context, '/booked', arguments: booking);
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final draft = widget.draft;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 16,
            offset: const Offset(0, -4),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
          child: ListenableBuilder(
            listenable: draft,
            builder: (context, _) {
              final total = widget.price + (draft.atHome ? widget.homeCollectionFee ?? 0 : 0);
              return PrimaryButton(
                label: draft.time == null
                    ? 'Pick a time to book'
                    : 'Book appointment (${rupees(total)})',
                busy: _sending,
                onPressed: draft.time == null ? null : _send,
              );
            },
          ),
        ),
      ),
    );
  }
}
