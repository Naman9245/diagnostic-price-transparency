import 'package:flutter/material.dart';

import '../api.dart';
import '../format.dart';
import '../models.dart';
import '../theme.dart';
import '../widgets/async_view.dart';
import '../widgets/common.dart';
import '../widgets/test_row.dart';

/// Every test as a round tile, three to a row. Home's "See all" opens it.
class TestsScreen extends StatefulWidget {
  const TestsScreen({super.key});

  @override
  State<TestsScreen> createState() => _TestsScreenState();
}

class _TestsScreenState extends State<TestsScreen> with Reloadable<TestsScreen, List<TestItem>> {
  @override
  Future<List<TestItem>> fetch() => Api.tests();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: pageBar(title: const Text('Find your test')),
      body: AsyncView(
        future: future,
        onRetry: reload,
        builder: (context, tests) => GridView.count(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 48),
          crossAxisCount: 3,
          childAspectRatio: 0.82,
          children: [for (final test in tests) _TestTile(test: test)],
        ),
      ),
    );
  }
}

class _TestTile extends StatelessWidget {
  const _TestTile({required this.test});

  final TestItem test;

  @override
  Widget build(BuildContext context) {
    return TapSurface(
      onTap: () => Navigator.pushNamed(context, '/test/${test.id}'),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(16))),
      child: Column(
        children: [
          const SizedBox(height: 10),
          CategoryIcon(category: test.category, size: 70),
          const SizedBox(height: 8),
          Text(
            test.shortName,
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700),
          ),
          if (test.minPrice != null) Text('from ${rupees(test.minPrice!)}', style: AppText.muted),
        ],
      ),
    );
  }
}
