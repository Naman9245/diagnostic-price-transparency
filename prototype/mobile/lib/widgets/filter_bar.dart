import 'package:flutter/material.dart';

import '../filters.dart';
import 'common.dart';

/// A row of chips that scrolls sideways under a page's title.
class ChipBar extends StatelessWidget {
  const ChipBar({super.key, required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 54,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
        children: children,
      ),
    );
  }
}

/// The lab filter chips, with an optional chip in front of them (the results
/// screen puts its sort chip there).
class FilterBar extends StatelessWidget {
  const FilterBar({
    super.key,
    required this.filters,
    required this.selected,
    required this.onToggle,
    this.leading,
  });

  final Iterable<LabFilter> filters;
  final Set<LabFilter> selected;
  final ValueChanged<LabFilter> onToggle;
  final Widget? leading;

  @override
  Widget build(BuildContext context) {
    return ChipBar(
      children: [
        ?leading,
        for (final filter in filters)
          FilterPill(
            label: filter.label,
            selected: selected.contains(filter),
            onTap: () => onToggle(filter),
          ),
      ],
    );
  }
}
