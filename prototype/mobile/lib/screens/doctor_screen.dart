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
import '../widgets/initials_avatar.dart';
import '../widgets/tree_avatar.dart';

/// One doctor, laid out like the design's doctor profile: who they are, what
/// a consultation costs and where, then a day and a time to book.
class DoctorScreen extends StatefulWidget {
  const DoctorScreen({super.key, required this.doctorId});

  final String doctorId;

  @override
  State<DoctorScreen> createState() => _DoctorScreenState();
}

class _DoctorScreenState extends State<DoctorScreen> with Reloadable<DoctorScreen, Doctor> {
  @override
  Future<Doctor> fetch() => Api.doctor(widget.doctorId, area: currentArea.value);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: pageBar(title: const Text('Doctor profile'), demo: true),
      body: AsyncView(
        future: future,
        onRetry: reload,
        builder: (context, doctor) => _DoctorPage(doctor: doctor),
      ),
    );
  }
}

/// The loaded page. It holds the booking draft, which needs the doctor's
/// own days and sessions.
class _DoctorPage extends StatefulWidget {
  const _DoctorPage({required this.doctor});

  final Doctor doctor;

  @override
  State<_DoctorPage> createState() => _DoctorPageState();
}

class _DoctorPageState extends State<_DoctorPage> {
  late final _draft = BookingDraft(
    timetable: widget.doctor.slots,
    weekdays: widget.doctor.weekdays,
  );

  @override
  void dispose() {
    _draft.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final doctor = widget.doctor;
    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
            children: [
              ProfileHeader(
                picture: InitialsAvatar(
                  name: doctor.name,
                  color: doctor.hospital.brandColor,
                  size: 76,
                ),
                name: doctor.name,
                detail: '${doctor.specialtyName} · ${doctor.qualifications}',
                rating: doctor.rating,
                reviews: doctor.reviews,
              ),
              const SizedBox(height: 14),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  MintPill(
                    icon: Icons.workspace_premium_outlined,
                    text: '${doctor.experienceYears} years’ experience',
                  ),
                  MintPill(icon: Icons.translate_rounded, text: doctor.languages.join(', ')),
                  MintPill(icon: Icons.calendar_month_outlined, text: doctor.days.join(', ')),
                ],
              ),
              const SizedBox(height: 20),
              const Text('About the doctor', style: AppText.section),
              const SizedBox(height: 6),
              Text(doctor.about, style: AppText.body),
              const SizedBox(height: 22),
              const Text('Consultation fee', style: AppText.section),
              const SizedBox(height: 10),
              _FeeCard(doctor: doctor),
              const SizedBox(height: 24),
              BookingPanel(draft: _draft),
            ],
          ),
        ),
        BookBar(
          draft: _draft,
          price: doctor.fee.amount,
          book: () => Api.bookDoctor(doctor, _draft),
        ),
      ],
    );
  }
}

/// What a consultation costs and where the fee came from, then the
/// hospital, which opens its own page.
class _FeeCard extends StatelessWidget {
  const _FeeCard({required this.doctor});

  final Doctor doctor;

  @override
  Widget build(BuildContext context) {
    final hospital = doctor.hospital;
    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: const BorderRadius.all(Radius.circular(16)),
        border: Border.all(color: AppColors.line),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Expanded(child: Text('In-person consultation', style: AppText.title)),
                Text(rupees(doctor.fee.amount), style: AppText.price.copyWith(fontSize: 19)),
              ],
            ),
            const SizedBox(height: 2),
            const Text('Paid at the hospital on the day', style: AppText.muted),
            const SizedBox(height: 14),
            const DashedDivider(),
            const SizedBox(height: 12),
            SourceLine(doctor.fee),
            const SizedBox(height: 8),
            TapSurface(
              onTap: () => Navigator.pushNamed(context, '/hospital/${hospital.id}'),
              shape: const RoundedRectangleBorder(
                borderRadius: BorderRadius.all(Radius.circular(12)),
              ),
              scale: 0.98,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Row(
                  children: [
                    TreeAvatar(color: hospital.brandColor, size: 44),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            hospital.name,
                            style: AppText.title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          const SizedBox(height: 4),
                          DemoLine('${hospital.area} · ${km(hospital.distanceKm)}'),
                        ],
                      ),
                    ),
                    const Icon(Icons.chevron_right_rounded, color: AppColors.slate),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
