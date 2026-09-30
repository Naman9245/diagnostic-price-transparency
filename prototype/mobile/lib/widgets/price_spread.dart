import 'dart:math';

import 'package:flutter/material.dart';

import '../theme.dart';

/// A strip from the cheapest lab to the priciest, with one dot per lab.
///
/// It's the point of the whole app in one picture: the same test costs very
/// different amounts nearby. [highlight] marks one lab's price with a bigger
/// black dot.
class PriceSpread extends StatelessWidget {
  const PriceSpread({super.key, required this.prices, this.highlight});

  final List<int> prices;
  final int? highlight;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: prices.isEmpty
          ? null
          : 'Prices range from ₹${prices.reduce(min)} to ₹${prices.reduce(max)}',
      child: SizedBox(
        height: 22,
        width: double.infinity,
        child: CustomPaint(painter: _SpreadPainter(prices, highlight)),
      ),
    );
  }
}

class _SpreadPainter extends CustomPainter {
  _SpreadPainter(this.prices, this.highlight);

  final List<int> prices;
  final int? highlight;

  @override
  void paint(Canvas canvas, Size size) {
    if (prices.isEmpty) return;
    final low = prices.reduce(min), high = prices.reduce(max);
    const pad = 10.0; // room for the end dots
    final y = size.height / 2;
    double xFor(int price) =>
        high == low ? size.width / 2 : pad + (price - low) / (high - low) * (size.width - 2 * pad);

    // The track runs from teal at the cheap end to coral at the pricey end.
    final track = Paint()
      ..strokeWidth = 6
      ..strokeCap = StrokeCap.round
      ..shader = const LinearGradient(colors: [AppColors.teal, AppColors.amber, AppColors.coral])
          .createShader(Rect.fromLTWH(pad, 0, size.width - 2 * pad, size.height));
    canvas.drawLine(Offset(pad, y), Offset(size.width - pad, y), track);

    // One hollow dot per lab.
    final fill = Paint()..color = Colors.white;
    final ring = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2
      ..color = AppColors.ink.withValues(alpha: 0.6);
    for (final price in prices) {
      final centre = Offset(xFor(price), y);
      canvas.drawCircle(centre, 5.5, fill);
      canvas.drawCircle(centre, 5.5, ring);
    }

    // The lab being looked at, on top.
    final highlighted = highlight;
    if (highlighted != null) {
      final centre = Offset(xFor(highlighted), y);
      canvas.drawCircle(centre, 9, Paint()..color = AppColors.ink);
      canvas.drawCircle(
        centre,
        9,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 3
          ..color = Colors.white,
      );
    }
  }

  @override
  bool shouldRepaint(_SpreadPainter old) => old.prices != prices || old.highlight != highlight;
}
