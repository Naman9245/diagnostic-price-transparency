import 'dart:math';

import 'package:flutter/material.dart';

import '../format.dart';
import '../models.dart';
import '../theme.dart';
import 'common.dart';
import 'price_spread.dart';
import 'test_row.dart';

/// A test's price at one lab: what the test checks, how to prepare, where
/// the price sits among labs nearby, and the document it came from.
class TestPriceCard extends StatelessWidget {
  const TestPriceCard({super.key, required this.test, required this.price, required this.nearby});

  final TestItem test;
  final Price price;

  /// What every lab nearby charges for the same test, this one included.
  final List<int> nearby;

  @override
  Widget build(BuildContext context) {
    final lowest = nearby.reduce(min);
    final isCheapest = price.amount == lowest;
    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: const BorderRadius.all(Radius.circular(16)),
        border: Border.all(color: AppColors.line),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                CategoryIcon(category: test.category, size: 40, square: true),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(test.name, style: AppText.title),
                      const SizedBox(height: 2),
                      Text(test.about, style: AppText.muted),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Text(rupees(price.amount), style: AppText.price.copyWith(fontSize: 19)),
              ],
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 16,
              runSpacing: 6,
              children: [
                _Meta(
                  test.hasPreparation
                      ? Icons.info_outline_rounded
                      : Icons.check_circle_outline_rounded,
                  test.preparation,
                ),
                _Meta(Icons.description_outlined, 'Report ${test.reportIn.toLowerCase()}'),
              ],
            ),
            const SizedBox(height: 16),
            PriceSpread(prices: nearby, highlight: price.amount),
            const SizedBox(height: 6),
            Text(
              isCheapest
                  ? 'The cheapest of ${nearby.length} labs nearby'
                  : '${rupees(price.amount - lowest)} more than the cheapest of ${nearby.length} labs nearby',
              style: TextStyle(
                fontSize: 12.5,
                fontWeight: FontWeight.w600,
                color: isCheapest ? AppColors.teal : AppColors.slate,
              ),
            ),
            const SizedBox(height: 14),
            const DashedDivider(),
            const SizedBox(height: 12),
            SourceLine(price),
          ],
        ),
      ),
    );
  }
}

class _Meta extends StatelessWidget {
  const _Meta(this.icon, this.text);

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 15, color: AppColors.slate),
        const SizedBox(width: 5),
        Text(text, style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w500)),
      ],
    );
  }
}
