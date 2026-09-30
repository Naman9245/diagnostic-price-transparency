import 'package:flutter/material.dart';

import '../format.dart';
import '../models.dart';
import '../theme.dart';
import 'common.dart';

/// A test in a list, laid out like a doctor in a booking app: its icon on
/// the left, what it checks in the middle, and the lowest price nearby with
/// a Compare button on the right.
class TestRow extends StatelessWidget {
  const TestRow({super.key, required this.test, required this.onTap});

  final TestItem test;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return TapSurface(
      onTap: onTap,
      shape: const RoundedRectangleBorder(),
      scale: 1,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        child: Row(
          children: [
            CategoryIcon(category: test.category, size: 52, square: true),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    test.name,
                    style: AppText.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    test.about,
                    style: AppText.muted,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${test.labCount} labs nearby',
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: AppColors.teal,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 10),
            if (test.minPrice != null)
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text.rich(
                    TextSpan(
                      children: [
                        const TextSpan(
                          text: 'from ',
                          style: TextStyle(fontSize: 11.5, color: AppColors.slate),
                        ),
                        TextSpan(text: rupees(test.minPrice!), style: AppText.price),
                      ],
                    ),
                  ),
                  const SizedBox(height: 6),
                  RowButton(label: 'Compare', onPressed: onTap),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

/// The category's icon, on white in a thin circle (the design's category
/// tiles) or on a soft tint of its colour in a rounded square (list rows).
class CategoryIcon extends StatelessWidget {
  const CategoryIcon({super.key, required this.category, required this.size, this.square = false});

  final String category;
  final double size;
  final bool square;

  @override
  Widget build(BuildContext context) {
    final (icon, color) = categoryStyle(category);
    return Container(
      width: size,
      height: size,
      decoration: square
          ? BoxDecoration(
              color: color.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(14),
            )
          : BoxDecoration(
              color: Colors.white,
              shape: BoxShape.circle,
              border: Border.all(color: AppColors.line),
            ),
      child: Icon(icon, color: color, size: size * 0.46),
    );
  }
}
