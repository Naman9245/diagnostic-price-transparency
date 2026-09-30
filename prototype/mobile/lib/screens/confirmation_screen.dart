import 'package:flutter/material.dart';

import '../format.dart';
import '../models.dart';
import '../theme.dart';
import '../widgets/common.dart';
import '../widgets/pressable.dart';
import 'shell.dart';

/// Shown after a booking goes through: what was booked, what it costs and
/// what to do beforehand.
class ConfirmationScreen extends StatelessWidget {
  const ConfirmationScreen({super.key, required this.booking});

  final Booking booking;

  @override
  Widget build(BuildContext context) {
    // Skip the pop-in when the phone is set to reduce motion.
    final animate = !MediaQuery.disableAnimationsOf(context);
    // What's booked, how it happens, what the price is for and where it's paid.
    final (what, how, priceFor, payAt) = booking.isDoctor
        ? ('Doctor', 'In-person consultation', 'Consultation fee', 'Pay at the hospital')
        : booking.homeCollection
        ? ('Test', 'Sample collected at home', 'Test price', 'Pay on collection')
        : ('Test', 'You visit the lab', 'Test price', 'Pay at the lab');
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 40, 20, 24),
          children: [
            Center(
              child: TweenAnimationBuilder<double>(
                tween: Tween(begin: animate ? 0 : 1, end: 1),
                duration: const Duration(milliseconds: 700),
                curve: Curves.elasticOut,
                builder: (context, scale, child) => Transform.scale(scale: scale, child: child),
                child: const CircleAvatar(
                  radius: 42,
                  backgroundColor: AppColors.teal,
                  child: Icon(Icons.check_rounded, color: Colors.white, size: 50),
                ),
              ),
            ),
            const SizedBox(height: 18),
            const Text('Booking confirmed', textAlign: TextAlign.center, style: AppText.heading),
            const SizedBox(height: 6),
            Text(
              'Booking ID ${booking.id}',
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.slate, letterSpacing: 0.5),
            ),
            const SizedBox(height: 24),
            Container(
              padding: const EdgeInsets.fromLTRB(16, 6, 16, 16),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: AppColors.line),
              ),
              child: Column(
                children: [
                  _Line(what, booking.title),
                  _Line('Where', booking.hospitalName),
                  _Line('When', '${shortDate(booking.date)} · ${clockTime(booking.time)}'),
                  _Line('How', how),
                  const SizedBox(height: 10),
                  const DashedDivider(),
                  const SizedBox(height: 4),
                  _Line(priceFor, rupees(booking.price)),
                  if (booking.homeCollection)
                    _Line(
                      'Home collection',
                      booking.homeCollectionFee == 0 ? 'Free' : rupees(booking.homeCollectionFee),
                    ),
                  _Line(payAt, rupees(booking.total), bold: true),
                ],
              ),
            ),
            if (booking.hasPreparation) ...[
              const SizedBox(height: 14),
              PrepNote(booking.preparation),
            ],
            const SizedBox(height: 28),
            PrimaryButton(
              label: 'See my bookings',
              onPressed: () => _backToTabs(context, ShellTab.bookings),
            ),
            const SizedBox(height: 4),
            Pressable(
              child: TextButton(
                onPressed: () => _backToTabs(context, ShellTab.home),
                child: const Text('Back to home'),
              ),
            ),
            const SizedBox(height: 10),
            const Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                DemoBadge(),
                SizedBox(width: 8),
                Text(
                  'A demo booking. No hospital was told.',
                  style: TextStyle(fontSize: 12.5, color: AppColors.slate),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Closes every page on top of the tabs and shows [tab].
void _backToTabs(BuildContext context, ShellTab tab) {
  shellTab.value = tab;
  Navigator.popUntil(context, (route) => route.isFirst);
}

class _Line extends StatelessWidget {
  const _Line(this.label, this.value, {this.bold = false});

  final String label, value;
  final bool bold;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 118, child: Text(label, style: AppText.muted)),
          Expanded(
            child: Text(
              value,
              textAlign: TextAlign.end,
              style: TextStyle(
                fontSize: bold ? 17 : 14,
                fontWeight: bold ? FontWeight.w800 : FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
