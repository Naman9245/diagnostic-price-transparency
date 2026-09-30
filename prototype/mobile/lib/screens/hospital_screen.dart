import 'package:flutter/material.dart';

import '../api.dart';
import '../booking_draft.dart';
import '../format.dart';
import '../location.dart';
import '../models.dart';
import '../theme.dart';
import '../widgets/async_view.dart';
import '../widgets/booking_panel.dart';
import '../widgets/common.dart';
import '../widgets/doctor_row.dart';
import '../widgets/test_price_card.dart';
import '../widgets/test_row.dart';
import '../widgets/tree_avatar.dart';

typedef _LabData = (List<TestItem>, List<Hospital>, List<Doctor>);

/// One lab, laid out like a doctor's profile in a booking app: who they are,
/// the chosen test's price and where it came from, then a day and a time to
/// book. Only partners can be booked; for everyone else it says why not.
/// Partners also list their doctors.
class HospitalScreen extends StatefulWidget {
  const HospitalScreen({super.key, required this.hospitalId, required this.testId});

  final String hospitalId, testId;

  @override
  State<HospitalScreen> createState() => _HospitalScreenState();
}

class _HospitalScreenState extends State<HospitalScreen> with Reloadable<HospitalScreen, _LabData> {
  final _draft = BookingDraft();
  final _scroll = ScrollController();

  /// The test on show. Tapping one under "Other tests here" changes it.
  late String _testId = widget.testId;

  /// Every lab with all its prices, so the spread for any test on this page
  /// can be drawn without another request, and this lab's doctors.
  @override
  Future<_LabData> fetch() async {
    final area = currentArea.value;
    final ((tests, labs), doctors) = await both(
      both(Api.tests(), Api.hospitals(area: area)),
      Api.doctors(area: area, hospitalId: widget.hospitalId),
    );
    return (tests, labs, doctors);
  }

  @override
  void dispose() {
    _draft.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _pickTest(String testId) {
    setState(() => _testId = testId);
    _draft.pickAtHome(false); // the new test may not allow home collection
    _scroll.animateTo(0, duration: const Duration(milliseconds: 300), curve: Curves.easeOut);
  }

  @override
  Widget build(BuildContext context) {
    return AsyncView(
      future: future,
      onRetry: reload,
      frame: (child) => Scaffold(
        appBar: pageBar(title: const Text('Lab profile')),
        body: child,
      ),
      builder: (context, data) {
        final (tests, labs, doctors) = data;
        // An unknown id never gets here: the doctors request fails with a 404.
        final lab = labs.firstWhere((h) => h.id == widget.hospitalId);
        final test = tests.firstWhere((t) => t.id == _testId, orElse: () => tests.first);
        return _page(lab, test, tests, labs, doctors);
      },
    );
  }

  Widget _page(
    Hospital lab,
    TestItem test,
    List<TestItem> tests,
    List<Hospital> labs,
    List<Doctor> doctors,
  ) {
    final price = lab.prices[test.id];
    // What every lab offering this test charges; `?` skips labs that don't.
    final nearby = [for (final other in labs) ?other.priceOf(test.id)];
    final others = tests.where((t) => t.id != test.id && lab.prices.containsKey(t.id));
    // Only partners can be booked, and only for a test they offer.
    final bookable = lab.partner ? price : null;
    final homeFee = lab.homeCollection && test.homeCollection ? lab.homeCollectionFee ?? 0 : null;

    return Scaffold(
      appBar: pageBar(title: const Text('Lab profile'), demo: true),
      body: ListView(
        controller: _scroll,
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        children: [
          ProfileHeader(
            picture: TreeAvatar(color: lab.brandColor, size: 76),
            name: lab.name,
            detail: '${lab.area} · ${km(lab.distanceKm)} away',
            rating: lab.rating,
            reviews: lab.reviews,
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              MintPill(icon: Icons.schedule_rounded, text: lab.openHours),
              if (lab.nabl) const MintPill(icon: Icons.verified_outlined, text: 'NABL accredited'),
              if (lab.homeCollection)
                MintPill(
                  icon: Icons.home_outlined,
                  text: lab.homeCollectionFee == 0
                      ? 'Free home collection'
                      : 'Home collection ${rupees(lab.homeCollectionFee!)}',
                ),
            ],
          ),
          const SizedBox(height: 20),
          const Text('About', style: AppText.section),
          const SizedBox(height: 6),
          Text(_about(lab), style: AppText.body),
          const SizedBox(height: 22),
          const Text('Your test', style: AppText.section),
          const SizedBox(height: 10),
          if (price == null)
            Text('This lab doesn’t offer ${test.name}.', style: AppText.muted)
          else
            TestPriceCard(test: test, price: price, nearby: nearby),
          const SizedBox(height: 24),
          if (bookable != null)
            BookingPanel(draft: _draft, homeCollectionFee: homeFee, preparation: test.preparation)
          else if (!lab.partner)
            const _NotBookable(),
          if (others.isNotEmpty) ...[
            const SizedBox(height: 24),
            const Text('Other tests here', style: AppText.section),
            const SizedBox(height: 4),
            for (final other in others)
              _OtherTest(
                test: other,
                price: lab.priceOf(other.id)!,
                onTap: () => _pickTest(other.id),
              ),
          ],
          if (doctors.isNotEmpty) ...[
            const SizedBox(height: 24),
            const Text('Doctors here', style: AppText.section),
            for (final doctor in doctors)
              DoctorRow(doctor: doctor, padding: const EdgeInsets.symmetric(vertical: 10)),
          ],
        ],
      ),
      bottomNavigationBar: bookable == null
          ? null
          : BookBar(
              draft: _draft,
              price: bookable.amount,
              homeCollectionFee: homeFee,
              book: () => Api.bookTest(lab, test, _draft),
            ),
    );
  }

  /// A short description built from what the data knows about the lab.
  static String _about(Hospital lab) {
    final hours = lab.openHours == 'Open 24 hours' ? 'open 24 hours' : 'open ${lab.openHours}';
    return [
      '${lab.name} is in ${lab.address}, Bengaluru, $hours.',
      if (lab.nabl) 'Its lab is NABL accredited.',
      if (lab.homeCollection) 'It can collect samples at home.',
      // Non-partners get a card further down saying why they can't be booked.
      if (lab.partner) 'It takes bookings through RateCard.',
    ].join(' ');
  }
}

/// Shown instead of the booking controls when the lab isn't a partner.
class _NotBookable extends StatelessWidget {
  const _NotBookable();

  @override
  Widget build(BuildContext context) {
    return const DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.cloud,
        borderRadius: BorderRadius.all(Radius.circular(14)),
      ),
      child: Padding(
        padding: EdgeInsets.all(14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.info_outline_rounded, color: AppColors.slate),
            SizedBox(width: 10),
            Expanded(
              child: Text(
                'This lab isn’t a RateCard partner, so it can’t be booked here. '
                'The price is from its published rate card.',
                style: TextStyle(fontSize: 13, color: AppColors.ink, height: 1.4),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Another test at this lab. Tapping it shows that test instead.
class _OtherTest extends StatelessWidget {
  const _OtherTest({required this.test, required this.price, required this.onTap});

  final TestItem test;
  final int price;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return TapSurface(
      onTap: onTap,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(12))),
      scale: 0.98,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          children: [
            CategoryIcon(category: test.category, size: 38, square: true),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                test.name,
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
              ),
            ),
            Text(rupees(price), style: AppText.price.copyWith(fontSize: 14.5)),
            const Icon(Icons.chevron_right_rounded, color: AppColors.slate),
          ],
        ),
      ),
    );
  }
}
