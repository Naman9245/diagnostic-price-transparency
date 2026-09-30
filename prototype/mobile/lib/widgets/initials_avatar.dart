import 'package:flutter/material.dart';

import '../format.dart';

/// A round stand-in for a photo: someone's initials in a dark shade of
/// [color], on a pale tint of it. The doctors here are made up, so they get
/// initials, never a face.
class InitialsAvatar extends StatelessWidget {
  const InitialsAvatar({super.key, required this.name, required this.color, this.size = 52});

  final String name;
  final Color color;
  final double size;

  @override
  Widget build(BuildContext context) {
    final hsl = HSLColor.fromColor(color);
    final ink = hsl.withLightness(0.25).toColor(); // dark enough to read on any tint
    final letters = initials(name);
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(shape: BoxShape.circle, color: hsl.withLightness(0.91).toColor()),
      // Someone who hasn't given a name yet gets a plain figure.
      child: letters.isEmpty
          ? Icon(Icons.person_rounded, size: size * 0.5, color: ink)
          : Text(
              letters,
              style: TextStyle(fontSize: size * 0.34, fontWeight: FontWeight.w800, color: ink),
            ),
    );
  }
}
