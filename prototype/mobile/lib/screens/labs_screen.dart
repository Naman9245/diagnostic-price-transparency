import 'package:flutter/material.dart';

import '../api.dart';
import '../filters.dart';
import '../location.dart';
import '../models.dart';
import '../theme.dart';
import '../widgets/async_view.dart';
import '../widgets/common.dart';
import '../widgets/filter_bar.dart';
import '../widgets/lab_row.dart';

/// Every lab near you, nearest first, with quick filters. Home's "See all"
/// opens it.
class LabsScreen extends StatefulWidget {
  const LabsScreen({super.key});

  @override
  State<LabsScreen> createState() => _LabsScreenState();
}

class _LabsScreenState extends State<LabsScreen> with Reloadable<LabsScreen, List<Hospital>> {
  final _filters = <LabFilter>{};

  @override
  Future<List<Hospital>> fetch() async =>
      (await Api.hospitals(area: currentArea.value))..sort(nearestFirst);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: pageBar(
        title: Column(
          children: [
            const Text('Labs'),
            Text(
              'near ${currentArea.value.name}',
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w500,
                color: AppColors.slate,
              ),
            ),
          ],
        ),
      ),
      body: Column(
        children: [
          FilterBar(
            filters: LabFilter.values,
            selected: _filters,
            onToggle: (filter) => setState(() => _filters.toggle(filter)),
          ),
          Expanded(
            child: AsyncView(
              future: future,
              onRetry: reload,
              builder: (context, all) {
                final labs = all.passing(_filters);
                return RefreshIndicator(
                  onRefresh: refresh,
                  child: labs.isEmpty
                      ? ListView(
                          physics: const AlwaysScrollableScrollPhysics(),
                          children: const [
                            SizedBox(height: 48),
                            Text(
                              'No labs match all of these filters.',
                              textAlign: TextAlign.center,
                              style: AppText.muted,
                            ),
                          ],
                        )
                      : ListView.separated(
                          physics: const AlwaysScrollableScrollPhysics(),
                          padding: const EdgeInsets.only(bottom: 48),
                          itemCount: labs.length,
                          separatorBuilder: (context, i) => const Divider(indent: 82),
                          itemBuilder: (context, i) => LabRow(
                            hospital: labs[i],
                            onOpen: () => Navigator.pushNamed(context, '/hospital/${labs[i].id}'),
                          ),
                        ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
