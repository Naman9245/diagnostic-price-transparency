import 'dart:math';

import 'package:flutter/material.dart';

/// A round picture standing in for a hospital's photo: the tree the hospital
/// is named after, in blossom, drawn in the hospital's colour.
///
/// Every demo hospital is named after one of Bengaluru's street trees, so
/// Jacaranda is purple, Tabebuia pink and Copperpod yellow.
class TreeAvatar extends StatelessWidget {
  const TreeAvatar({super.key, required this.color, this.size = 52});

  final Color color;
  final double size;

  @override
  Widget build(BuildContext context) {
    return SizedBox.square(
      dimension: size,
      child: CustomPaint(painter: _TreePainter(color)),
    );
  }
}

class _TreePainter extends CustomPainter {
  _TreePainter(this.color);

  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    final hsl = HSLColor.fromColor(color);
    // The hospital's colour at another lightness, optionally less saturated.
    Color shade(double lightness, [double saturation = 1]) => hsl
        .withLightness(lightness.clamp(0.0, 0.95))
        .withSaturation(min(hsl.saturation, saturation))
        .toColor();

    canvas.save();
    canvas.clipPath(Path()..addOval(Offset.zero & size));

    // A pale sky and a gentle hill.
    canvas.drawRect(Offset.zero & size, Paint()..color = shade(0.93, 0.5));
    canvas.drawCircle(Offset(w / 2, h * 1.45), w * 0.62, Paint()..color = shade(0.84, 0.35));

    // The trunk.
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromCenter(center: Offset(w / 2, h * 0.7), width: w * 0.09, height: h * 0.34),
        Radius.circular(w * 0.03),
      ),
      Paint()..color = const Color(0xFF6E4B32),
    );

    // The canopy: overlapping circles, darker at the back, lighter in front.
    final r = w * 0.19;
    final top = Offset(w / 2, h * 0.42);
    final lobes = [
      (Offset(-r * 0.9, r * 0.25), r * 0.72, shade(hsl.lightness - 0.1)),
      (Offset(r * 0.9, r * 0.3), r * 0.7, shade(hsl.lightness - 0.1)),
      (Offset(0, -r * 0.35), r * 0.88, color),
      (Offset(-r * 0.45, r * 0.3), r * 0.8, color),
      (Offset(r * 0.45, r * 0.38), r * 0.74, shade(hsl.lightness + 0.08)),
    ];
    for (final (offset, radius, colour) in lobes) {
      canvas.drawCircle(top + offset, radius, Paint()..color = colour);
    }

    // A few petals catching the light.
    final petal = Paint()..color = Colors.white.withValues(alpha: 0.6);
    const spots = [(-0.55, -0.1), (0.2, -0.6), (0.6, 0.15), (-0.1, 0.35), (0.25, -0.05)];
    for (final (dx, dy) in spots) {
      canvas.drawCircle(top + Offset(dx * r, dy * r), r * 0.1, petal);
    }

    canvas.restore();
  }

  @override
  bool shouldRepaint(_TreePainter old) => old.color != color;
}
