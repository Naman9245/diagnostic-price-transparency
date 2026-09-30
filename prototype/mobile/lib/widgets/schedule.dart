import 'package:flutter/material.dart';

import '../format.dart';
import '../theme.dart';
import 'common.dart';

const _chipShape = RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(14)));

/// A week of days to pick from, like a booking app's date strip. Days with
/// no open slots left (late today, say) are greyed out and can't be picked.
class DayStrip extends StatelessWidget {
  const DayStrip({
    super.key,
    required this.days,
    required this.selected,
    required this.onSelect,
    required this.isOpen,
  });

  final List<DateTime> days;
  final DateTime selected;
  final ValueChanged<DateTime> onSelect;
  final bool Function(DateTime day) isOpen;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 70,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: days.length,
        separatorBuilder: (context, i) => const SizedBox(width: 8),
        itemBuilder: (context, i) {
          final day = days[i];
          final isSelected = day == selected;
          final open = isOpen(day);
          final color = switch ((isSelected, open)) {
            (true, _) => Colors.white,
            (false, true) => AppColors.ink,
            (false, false) => AppColors.slate.withValues(alpha: 0.45),
          };
          return TapSurface(
            onTap: open ? () => onSelect(day) : null,
            selected: isSelected,
            color: isSelected ? AppColors.teal : AppColors.cloud,
            shape: _chipShape,
            child: SizedBox(
              width: 54,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    '${day.day}',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: color),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    i == 0 ? 'Today' : weekday(day),
                    style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: color),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

/// Time slots as chips; the chosen one is filled teal.
class TimeChips extends StatelessWidget {
  const TimeChips({super.key, required this.slots, required this.selected, required this.onSelect});

  /// Times as "HH:MM".
  final List<String> slots;
  final String? selected;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final slot in slots)
          TapSurface(
            onTap: () => onSelect(slot),
            selected: slot == selected,
            color: slot == selected ? AppColors.teal : AppColors.cloud,
            shape: _chipShape,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: Text(
                clockTime(slot),
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: slot == selected ? Colors.white : AppColors.ink,
                ),
              ),
            ),
          ),
      ],
    );
  }
}
