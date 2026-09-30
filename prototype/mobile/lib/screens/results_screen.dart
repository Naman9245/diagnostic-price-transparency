import 'dart:math';

import 'package:flutter/material.dart';

import '../api.dart';
import '../filters.dart';
import '../format.dart';
import '../location.dart';
import '../models.dart';
import '../theme.dart';
import '../widgets/async_view.dart';
import '../widgets/common.dart';
import '../widgets/filter_bar.dart';
import '../widgets/lab_row.dart';
import '../widgets/price_spread.dart';

typedef _Results = (TestItem, List<Hospital>);

/// Every lab near you that offers one test, with sort and filter controls.
class ResultsScreen extends StatefulWidget {
  const ResultsScreen({super.key, required this.testId});

  final String testId;

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen> with Reloadable<ResultsScreen, _Results> {
  SortBy _sort = SortBy.cheapest;
  final _filters = <LabFilter>{};

  @override
  Future<_Results> fetch() async {
    // Both at once. An unknown test id makes the hospitals request fail with
    // the API's own "No test with id" message.
    final (tests, labs) = await both(
      Api.tests(),
      Api.hospitals(area: currentArea.value, testId: widget.testId),
    );
    return (tests.firstWhere((t) => t.id == widget.testId), labs);
  }

  Future<void> _pickSort() async {
    final choice = await showModalBottomSheet<SortBy>(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(20, 0, 20, 8),
              child: Text('Sort by', style: AppText.section),
            ),
            for (final option in SortBy.values)
              ListTile(
                contentPadding: const EdgeInsets.symmetric(horizontal: 20),
                title: Text(option.label),
                trailing: Icon(
                  option == _sort ? Icons.radio_button_checked : Icons.radio_button_unchecked,
                  color: option == _sort ? AppColors.teal : AppColors.slate,
                ),
                onTap: () => Navigator.pop(context, option),
              ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    if (choice != null) setState(() => _sort = choice);
  }

  @override
  Widget build(BuildContext context) {
    return AsyncView(
      future: future,
      onRetry: reload,
      frame: (child) => Scaffold(
        appBar: pageBar(title: const Text('Labs near you')),
        body: child,
      ),
      builder: (context, data) {
        final (test, labs) = data;
        final visible = labs.passing(_filters)..sort((a, b) => _sort.compare(a, b, test.id));
        return Scaffold(
          appBar: pageBar(
            title: _Title(test: test, count: visible.length),
          ),
          body: RefreshIndicator(onRefresh: refresh, child: _results(test, labs, visible)),
        );
      },
    );
  }

  Widget _results(TestItem test, List<Hospital> labs, List<Hospital> visible) {
    if (labs.isEmpty) {
      return const Center(child: Text('No lab nearby offers this test yet.', style: AppText.muted));
    }
    final prices = [for (final lab in labs) lab.priceOf(test.id)!];
    final lowest = prices.reduce(min), highest = prices.reduce(max);
    return CustomScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      slivers: [
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 6),
            child: _SpreadCard(prices: prices, lowest: lowest, highest: highest),
          ),
        ),
        // The chips stay pinned under the app bar while the list scrolls.
        SliverPersistentHeader(
          pinned: true,
          delegate: _PinnedBar(
            child: FilterBar(
              // Home collection means nothing for a test that can't be done at home.
              filters: LabFilter.values.where(
                (f) => f != LabFilter.homeCollection || test.homeCollection,
              ),
              selected: _filters,
              onToggle: (filter) => setState(() => _filters.toggle(filter)),
              leading: FilterPill(
                label: _sort.chipLabel,
                icon: Icons.swap_vert_rounded,
                trailingIcon: Icons.keyboard_arrow_down_rounded,
                selected: _sort != SortBy.cheapest,
                onTap: _pickSort,
              ),
            ),
          ),
        ),
        if (visible.isEmpty)
          SliverToBoxAdapter(child: _NoMatches(onClear: () => setState(_filters.clear)))
        else
          SliverList.separated(
            itemCount: visible.length,
            separatorBuilder: (context, i) => const Divider(indent: 82),
            itemBuilder: (context, i) {
              final lab = visible[i];
              final price = lab.priceOf(test.id)!;
              return LabRow(
                hospital: lab,
                price: price,
                note: _PriceNote(price: price, lowest: lowest, highest: highest),
                onOpen: () => Navigator.pushNamed(context, '/hospital/${lab.id}?test=${test.id}'),
              );
            },
          ),
        const SliverToBoxAdapter(child: SizedBox(height: 32)),
      ],
    );
  }
}

class _Title extends StatelessWidget {
  const _Title({required this.test, required this.count});

  final TestItem test;
  final int count;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(test.name, maxLines: 1, overflow: TextOverflow.ellipsis),
        Text(
          '$count ${count == 1 ? 'lab' : 'labs'} near ${currentArea.value.name}',
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: AppColors.slate),
        ),
      ],
    );
  }
}

/// The price spread for this test across every lab nearby.
class _SpreadCard extends StatelessWidget {
  const _SpreadCard({required this.prices, required this.lowest, required this.highest});

  final List<int> prices;
  final int lowest, highest;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: AppColors.mint,
        borderRadius: BorderRadius.all(Radius.circular(16)),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Same test, up to ${(highest / lowest).toStringAsFixed(1)}× the price',
              style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 12),
            PriceSpread(prices: prices),
            const SizedBox(height: 8),
            Row(
              children: [
                _End(price: lowest, label: 'cheapest', color: AppColors.teal),
                const Spacer(),
                _End(price: highest, label: 'priciest', color: AppColors.coral, alignEnd: true),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _End extends StatelessWidget {
  const _End({
    required this.price,
    required this.label,
    required this.color,
    this.alignEnd = false,
  });

  final int price;
  final String label;
  final Color color;
  final bool alignEnd;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: alignEnd ? CrossAxisAlignment.end : CrossAxisAlignment.start,
      children: [
        Text(
          rupees(price),
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: color),
        ),
        Text(label, style: const TextStyle(fontSize: 12, color: AppColors.slate)),
      ],
    );
  }
}

/// How one lab's price compares to the rest, said in rupees.
class _PriceNote extends StatelessWidget {
  const _PriceNote({required this.price, required this.lowest, required this.highest});

  final int price, lowest, highest;

  @override
  Widget build(BuildContext context) {
    final (icon, text, color) = price == lowest
        ? (Icons.check_circle_rounded, 'Cheapest nearby', AppColors.teal)
        : price == highest
        ? (
            Icons.north_east_rounded,
            '${rupees(price - lowest)} more than the cheapest',
            AppColors.coral,
          )
        : (
            Icons.sell_outlined,
            '${rupees(highest - price)} less than the priciest',
            AppColors.teal,
          );
    return Row(
      children: [
        Icon(icon, size: 14, color: color),
        const SizedBox(width: 4),
        Flexible(
          child: Text(
            text,
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color),
          ),
        ),
      ],
    );
  }
}

class _NoMatches extends StatelessWidget {
  const _NoMatches({required this.onClear});

  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 40, 24, 24),
      child: Column(
        children: [
          const Text(
            'No labs match all of these filters.',
            textAlign: TextAlign.center,
            style: AppText.section,
          ),
          const SizedBox(height: 12),
          TapSurface(
            onTap: onClear,
            color: Colors.white,
            shape: const StadiumBorder(side: BorderSide(color: AppColors.teal)),
            child: const Padding(
              padding: EdgeInsets.symmetric(horizontal: 18, vertical: 10),
              child: Text(
                'Clear filters',
                style: TextStyle(fontWeight: FontWeight.w700, color: AppColors.teal),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Keeps the filter bar pinned to the top of the scroll view.
class _PinnedBar extends SliverPersistentHeaderDelegate {
  _PinnedBar({required this.child});

  final Widget child;

  @override
  double get minExtent => 54;

  @override
  double get maxExtent => 54;

  @override
  Widget build(BuildContext context, double shrinkOffset, bool overlapsContent) {
    return Material(color: Colors.white, elevation: overlapsContent ? 1 : 0, child: child);
  }

  @override
  bool shouldRebuild(_PinnedBar oldDelegate) => true;
}
