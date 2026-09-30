import 'package:flutter/material.dart';

import '../api.dart';
import '../models.dart';
import '../theme.dart';
import '../widgets/async_view.dart';
import '../widgets/common.dart';
import '../widgets/search_field.dart';
import '../widgets/test_row.dart';

/// Search: type the test written on your doctor's slip. Every test can be
/// found by the other names labs print for it, so "haemogram" finds the CBC.
class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> with Reloadable<SearchScreen, List<TestItem>> {
  final _query = TextEditingController();

  @override
  Future<List<TestItem>> fetch() => Api.tests();

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  String get _text => _query.text.trim();

  void _open(TestItem test) => Navigator.pushNamed(context, '/test/${test.id}');

  /// Pressing Enter opens the first match straight away.
  Future<void> _openFirstMatch() async {
    final List<TestItem> tests;
    try {
      tests = await future;
    } catch (_) {
      return; // the error is already on screen
    }
    final first = tests.where((test) => test.matches(_text)).firstOrNull;
    if (first != null && mounted) _open(first);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: const BackCircle(),
        leadingWidth: 64,
        titleSpacing: 0,
        centerTitle: false,
        title: SearchField(
          controller: _query,
          hint: 'Search a test, like CBC or LFT',
          autofocus: true,
          onChanged: (_) => setState(() {}),
          onSubmitted: (_) => _openFirstMatch(),
        ),
        actions: const [SizedBox(width: 16)],
      ),
      body: AsyncView(
        future: future,
        onRetry: reload,
        builder: (context, tests) {
          final matches = tests.where((test) => test.matches(_text)).toList();
          return ListView(
            padding: const EdgeInsets.only(bottom: 24),
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                child: SectionHeader(switch ((_text.isEmpty, matches.isEmpty)) {
                  (true, _) => 'All tests',
                  (false, true) => 'No matches',
                  (false, false) => 'Matching tests',
                }),
              ),
              if (matches.isEmpty)
                Padding(
                  padding: const EdgeInsets.fromLTRB(24, 12, 24, 0),
                  child: Text(
                    'Nothing called “$_text” yet. Try the short name on your slip, like CBC or LFT.',
                    textAlign: TextAlign.center,
                    style: AppText.muted,
                  ),
                ),
              for (final test in matches) TestRow(test: test, onTap: () => _open(test)),
            ],
          );
        },
      ),
    );
  }
}
