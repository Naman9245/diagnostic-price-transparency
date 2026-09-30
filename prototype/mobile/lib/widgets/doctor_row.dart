import 'package:flutter/material.dart';

import '../format.dart';
import '../models.dart';
import '../theme.dart';
import 'common.dart';
import 'initials_avatar.dart';
import 'listing_row.dart';

/// A doctor in a list, laid out like a lab: initials in their hospital's
/// colour on the left, who and where they are in the middle, and the
/// consultation fee with Book Now on the right. Both open their page.
class DoctorRow extends StatelessWidget {
  const DoctorRow({super.key, required this.doctor, this.padding});

  final Doctor doctor;

  /// See [ListingRow.padding].
  final EdgeInsets? padding;

  @override
  Widget build(BuildContext context) {
    void open() => Navigator.pushNamed(context, '/doctor/${doctor.id}');
    return ListingRow(
      onTap: open,
      padding: padding,
      picture: InitialsAvatar(name: doctor.name, color: doctor.hospital.brandColor, size: 54),
      details: [
        Text(doctor.name, style: AppText.title, maxLines: 1, overflow: TextOverflow.ellipsis),
        const SizedBox(height: 2),
        Text(
          '${doctor.specialtyName} · ${doctor.experienceYears} yrs',
          style: AppText.muted,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: 4),
        DemoLine('${doctor.hospital.name} · ${km(doctor.hospital.distanceKm)}'),
        const SizedBox(height: 5),
        Rating(doctor.rating, count: doctor.reviews),
      ],
      price: Text(rupees(doctor.fee.amount), style: AppText.price),
      button: RowButton(label: 'Book Now', onPressed: open),
    );
  }
}
