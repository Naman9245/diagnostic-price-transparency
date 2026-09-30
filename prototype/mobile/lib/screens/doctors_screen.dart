import 'package:flutter/material.dart';

import '../api.dart';
import '../location.dart';
import '../models.dart';
import '../widgets/async_view.dart';
import '../widgets/common.dart';
import '../widgets/doctor_row.dart';
import '../widgets/filter_bar.dart';
import '../widgets/search_field.dart';

typedef _Doctors = (List<Specialty>, List<Doctor>);

/// Doctors near you, nearest first, to search by name or narrow to one
/// specialty. It's the Doctors tab, and the page a specialty on Home opens.
class DoctorsScreen extends StatefulWidget {
  const DoctorsScreen({super.key, this.specialty});

  /// The id of the specialty picked when the page opens, or null for all.
  final String? specialty;

  @override
  State<DoctorsScreen> createState() => _DoctorsScreenState();
}

class _DoctorsScreenState extends State<DoctorsScreen> with Reloadable<DoctorsScreen, _Doctors> {
  final _query = TextEditingController();
  late String? _specialty = widget.specialty;

  @override
  Future<_Doctors> fetch() => both(Api.specialties(), Api.doctors(area: currentArea.value));

  @override
  Listenable get reloadOn => currentArea;

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  void _showAll() => setState(() {
    _query.clear();
    _specialty = null;
  });

  @override
  Widget build(BuildContext context) {
    const title = Text('Find your doctor');
    return Scaffold(
      // A page opened from Home has a back button; the tab doesn't.
      appBar: ModalRoute.canPopOf(context) ?? false
          ? pageBar(title: title)
          : AppBar(automaticallyImplyLeading: false, title: title),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
            child: SearchField(
              controller: _query,
              hint: 'Search a doctor or specialty',
              onChanged: (_) => setState(() {}),
            ),
          ),
          Expanded(
            child: AsyncView(
              future: future,
              onRetry: reload,
              builder: (context, data) => _results(data.$1, data.$2),
            ),
          ),
        ],
      ),
    );
  }

  Widget _results(List<Specialty> specialties, List<Doctor> doctors) {
    final visible = [
      for (final doctor in doctors)
        if ((_specialty == null || doctor.specialty == _specialty) && doctor.matches(_query.text))
          doctor,
    ];
    return Column(
      children: [
        ChipBar(
          children: [
            FilterPill(
              label: 'All',
              selected: _specialty == null,
              onTap: () => setState(() => _specialty = null),
            ),
            for (final specialty in specialties)
              FilterPill(
                label: specialty.name,
                selected: specialty.id == _specialty,
                onTap: () => setState(() => _specialty = specialty.id),
              ),
          ],
        ),
        Expanded(
          child: visible.isEmpty
              ? EmptyState(
                  icon: Icons.person_search_outlined,
                  title: 'No doctors found',
                  message: 'Try another name or specialty.',
                  action: 'Show all doctors',
                  onAction: _showAll,
                )
              : RefreshIndicator(
                  onRefresh: refresh,
                  child: ListView.separated(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.only(bottom: 48),
                    itemCount: visible.length,
                    separatorBuilder: (context, i) => const Divider(indent: 82),
                    itemBuilder: (context, i) => DoctorRow(doctor: visible[i]),
                  ),
                ),
        ),
      ],
    );
  }
}
