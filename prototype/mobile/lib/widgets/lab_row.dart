import 'package:flutter/material.dart';

import '../format.dart';
import '../models.dart';
import '../theme.dart';
import 'common.dart';
import 'listing_row.dart';
import 'tree_avatar.dart';

/// A lab in a list, laid out like a doctor in a booking app: its picture on
/// the left, name, place and rating in the middle, and the price with a
/// button on the right. Only partners get "Book Now"; the rest get "View".
class LabRow extends StatelessWidget {
  const LabRow({super.key, required this.hospital, required this.onOpen, this.price, this.note});

  final Hospital hospital;
  final VoidCallback onOpen;

  /// The chosen test's price here, when the list is for one test.
  final int? price;

  /// An extra line under the rating, such as "Cheapest nearby".
  final Widget? note;

  @override
  Widget build(BuildContext context) {
    return ListingRow(
      onTap: onOpen,
      picture: TreeAvatar(color: hospital.brandColor, size: 54),
      details: [
        Text(hospital.name, style: AppText.title, maxLines: 1, overflow: TextOverflow.ellipsis),
        const SizedBox(height: 4),
        DemoLine('${hospital.area} · ${km(hospital.distanceKm)}'),
        const SizedBox(height: 5),
        Rating(hospital.rating, count: hospital.reviews),
        if (note != null) ...[const SizedBox(height: 6), note!],
      ],
      price: price != null
          ? Text(rupees(price!), style: AppText.price)
          : Text('${hospital.prices.length} tests', style: AppText.muted),
      button: RowButton(
        label: hospital.partner ? 'Book Now' : 'View',
        filled: hospital.partner,
        onPressed: onOpen,
      ),
    );
  }
}
