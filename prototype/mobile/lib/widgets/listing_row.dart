import 'package:flutter/material.dart';

import 'common.dart';

/// The layout the lab and doctor lists share, taken from the design's doctor
/// list: a picture on the left, details in the middle, and a price over a
/// button on the right. Tapping anywhere does what the button does.
class ListingRow extends StatelessWidget {
  const ListingRow({
    super.key,
    required this.onTap,
    required this.picture,
    required this.details,
    required this.price,
    required this.button,
    this.padding,
  });

  final VoidCallback onTap;
  final Widget picture, price, button;
  final List<Widget> details;

  /// Room around the row. By default it runs edge to edge with the list's
  /// margins inside; a page that has its own margins can trim the sides.
  final EdgeInsets? padding;

  @override
  Widget build(BuildContext context) {
    return TapSurface(
      onTap: onTap,
      shape: const RoundedRectangleBorder(),
      scale: 1,
      child: Padding(
        padding: padding ?? const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            picture,
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: details),
            ),
            const SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [price, const SizedBox(height: 8), button],
            ),
          ],
        ),
      ),
    );
  }
}
