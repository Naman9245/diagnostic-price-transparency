import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api.dart';
import '../filters.dart';
import '../format.dart';
import '../location.dart';
import '../models.dart';
import '../session.dart';
import '../theme.dart';
import '../widgets/area_sheet.dart';
import '../widgets/async_view.dart';
import '../widgets/common.dart';
import '../widgets/doctor_row.dart';
import '../widgets/lab_row.dart';
import '../widgets/pressable.dart';
import '../widgets/test_row.dart';
import 'shell.dart';

typedef _HomeData = ({
  List<TestItem> tests,
  List<Hospital> labs,
  List<Specialty> specialties,
  List<Doctor> doctors,
});

/// The Home tab: where you are, a search box for the test on your doctor's
/// slip, and shortcuts to tests, doctors and labs nearby.
///
/// It's deliberately not a feed. People arrive knowing which test they need,
/// so search comes first.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with Reloadable<HomeScreen, _HomeData> {
  @override
  Future<_HomeData> fetch() async {
    final area = currentArea.value;
    final ((tests, labs), (specialties, doctors)) = await both(
      both(Api.tests(), Api.hospitals(area: area)),
      both(Api.specialties(), Api.doctors(area: area)),
    );
    return (
      tests: tests,
      labs: labs..sort(nearestFirst),
      specialties: specialties,
      doctors: doctors,
    );
  }

  // The labs and doctors near you depend on where you are.
  @override
  Listenable get reloadOn => currentArea;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: refresh,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(0, 12, 0, 40),
            children: [
              const Padding(padding: EdgeInsets.symmetric(horizontal: 16), child: _Header()),
              const Padding(padding: EdgeInsets.fromLTRB(16, 16, 16, 0), child: _SearchBox()),
              const Padding(padding: EdgeInsets.fromLTRB(16, 12, 16, 0), child: DemoNotice()),
              AsyncView(
                future: future,
                onRetry: reload,
                builder: (context, data) => _Content(data),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Content extends StatelessWidget {
  const _Content(this.data);

  final _HomeData data;

  /// The best rated of the six doctors nearest you.
  static List<Doctor> _topDoctors(List<Doctor> nearestFirst) =>
      (nearestFirst.take(6).toList()..sort((a, b) => b.rating.compareTo(a.rating)))
          .take(3)
          .toList();

  @override
  Widget build(BuildContext context) {
    void open(String route) => Navigator.pushNamed(context, route);
    void openTest(TestItem test) => open('/test/${test.id}');
    final bannerTest = _Banner.pick(data.tests);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (bannerTest != null)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 18, 16, 0),
            child: _Banner(test: bannerTest, onCompare: () => openTest(bannerTest)),
          ),
        _header('Find your test', onSeeAll: () => open('/tests')),
        _circles([
          for (final test in data.tests.take(4))
            _CategoryCircle(
              category: test.category,
              label: test.shortName,
              onTap: () => openTest(test),
            ),
        ]),
        _header('Find a doctor', onSeeAll: () => shellTab.value = ShellTab.doctors),
        _circles([
          for (final specialty in data.specialties.take(4))
            _CategoryCircle(
              category: specialty.id,
              label: specialty.shortName,
              onTap: () => open('/doctors?specialty=${specialty.id}'),
            ),
        ]),
        _header('Top doctors near you', bottom: 2),
        for (final doctor in _topDoctors(data.doctors)) DoctorRow(doctor: doctor),
        _header('Labs near you', onSeeAll: () => open('/labs'), bottom: 2),
        for (final lab in data.labs.take(3))
          LabRow(hospital: lab, onOpen: () => open('/hospital/${lab.id}')),
      ],
    );
  }

  static Widget _header(String title, {VoidCallback? onSeeAll, double bottom = 12}) => Padding(
    padding: EdgeInsets.fromLTRB(16, 22, 16, bottom),
    child: SectionHeader(title, action: onSeeAll == null ? null : 'See all', onAction: onSeeAll),
  );

  /// Four round tiles side by side.
  static Widget _circles(List<Widget> tiles) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 8),
    child: Row(children: [for (final tile in tiles) Expanded(child: tile)]),
  );
}

/// Where you are, which you can change, and the emergency number. Signed
/// in, it greets you by name.
class _Header extends StatelessWidget {
  const _Header();

  /// The app is for planned tests, not emergencies. This is its one
  /// emergency path: a single tap opens the dialler on 108, the ambulance
  /// number, without asking anything first.
  Future<void> _callEmergency(BuildContext context) async {
    final opened = await launchUrl(Uri.parse('tel:108')).catchError((_) => false);
    if (!opened && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Couldn’t open the dialler. Call 108 from your phone.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Align(
            alignment: Alignment.centerLeft,
            child: TapSurface(
              onTap: () => pickArea(context),
              shape: const RoundedRectangleBorder(
                borderRadius: BorderRadius.all(Radius.circular(12)),
              ),
              scale: 0.97,
              child: ListenableBuilder(
                listenable: Listenable.merge([currentArea, currentUser]),
                builder: (context, _) => Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const CircleAvatar(
                      radius: 22,
                      backgroundColor: AppColors.mint,
                      child: Icon(Icons.location_on_rounded, color: AppColors.teal),
                    ),
                    const SizedBox(width: 10),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(switch (currentUser.value?.firstName) {
                          final name? => 'Hi, $name',
                          null => 'Prices near',
                        }, style: AppText.muted),
                        Row(
                          children: [
                            Text(
                              currentArea.value.name,
                              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                            ),
                            const Icon(Icons.keyboard_arrow_down_rounded, size: 20),
                          ],
                        ),
                      ],
                    ),
                    const SizedBox(width: 6),
                  ],
                ),
              ),
            ),
          ),
        ),
        Tooltip(
          message: 'Emergency? Call 108 for an ambulance',
          child: Pressable(
            child: OutlinedButton.icon(
              onPressed: () => _callEmergency(context),
              icon: const Icon(Icons.call_rounded, size: 16, color: AppColors.coral),
              label: const Text('108'),
              style: OutlinedButton.styleFrom(
                foregroundColor: AppColors.ink,
                side: const BorderSide(color: AppColors.line),
                shape: const StadiumBorder(),
                padding: const EdgeInsets.symmetric(horizontal: 14),
                minimumSize: const Size(0, 40),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

/// Looks like a search box; tapping it opens the search screen.
class _SearchBox extends StatelessWidget {
  const _SearchBox();

  @override
  Widget build(BuildContext context) {
    return TapSurface(
      onTap: () => Navigator.pushNamed(context, '/search'),
      color: AppColors.cloud,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(14))),
      scale: 0.98,
      child: const Padding(
        padding: EdgeInsets.symmetric(horizontal: 14, vertical: 15),
        child: Row(
          children: [
            Icon(Icons.search_rounded, color: AppColors.teal),
            SizedBox(width: 10),
            Text(
              'Search a test, like CBC or LFT',
              style: TextStyle(fontSize: 14.5, color: AppColors.slate),
            ),
          ],
        ),
      ),
    );
  }
}

/// The teal banner: the test whose price varies most, in plain numbers.
class _Banner extends StatelessWidget {
  const _Banner({required this.test, required this.onCompare});

  final TestItem test;
  final VoidCallback onCompare;

  /// The test with the widest gap between its cheapest and priciest lab.
  static TestItem? pick(List<TestItem> tests) {
    final priced = tests.where((t) => t.minPrice != null);
    if (priced.isEmpty) return null;
    return priced.reduce((a, b) => _gap(a) >= _gap(b) ? a : b);
  }

  static double _gap(TestItem t) => t.maxPrice! / t.minPrice!;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        borderRadius: BorderRadius.all(Radius.circular(18)),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [AppColors.teal, AppColors.tealDark],
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(18, 18, 14, 18),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Same test,\ndifferent price',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      height: 1.25,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    '${test.name} costs ${rupees(test.minPrice!)} at one lab '
                    'and ${rupees(test.maxPrice!)} at another.',
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.85),
                      fontSize: 12.5,
                      height: 1.4,
                    ),
                  ),
                  const SizedBox(height: 12),
                  TapSurface(
                    onTap: onCompare,
                    color: Colors.white,
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                      child: Text(
                        'Compare ${test.labCount} labs',
                        style: const TextStyle(
                          color: AppColors.teal,
                          fontSize: 12.5,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            // Where the reference design has a photo, this has the number.
            _GapBadge(gap: _gap(test)),
          ],
        ),
      ),
    );
  }
}

class _GapBadge extends StatelessWidget {
  const _GapBadge({required this.gap});

  final double gap;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 96,
      height: 96,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: Colors.white.withValues(alpha: 0.14),
        border: Border.all(color: Colors.white.withValues(alpha: 0.3), width: 1.5),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            '${gap.toStringAsFixed(1)}×',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 27,
              fontWeight: FontWeight.w800,
              height: 1,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'price gap',
            style: TextStyle(color: Colors.white.withValues(alpha: 0.8), fontSize: 11),
          ),
        ],
      ),
    );
  }
}

/// A test's category or a doctor's specialty as a round tile, with its name
/// underneath.
class _CategoryCircle extends StatelessWidget {
  const _CategoryCircle({required this.category, required this.label, required this.onTap});

  final String category, label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return TapSurface(
      onTap: onTap,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(16))),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Column(
          children: [
            CategoryIcon(category: category, size: 60),
            const SizedBox(height: 8),
            Text(
              label,
              textAlign: TextAlign.center,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 12.5,
                fontWeight: FontWeight.w600,
                color: AppColors.slate,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
