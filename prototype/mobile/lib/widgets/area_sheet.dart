import 'package:flutter/material.dart';

import '../location.dart';
import '../theme.dart';

/// Asks where you are, from the areas the demo knows, and makes it the
/// [currentArea]. Home's header and the Profile tab both open it.
Future<void> pickArea(BuildContext context) async {
  final picked = await showModalBottomSheet<Area>(
    context: context,
    builder: (context) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Padding(
            padding: EdgeInsets.fromLTRB(20, 0, 20, 4),
            child: Text('Where are you?', style: AppText.section),
          ),
          const Padding(
            padding: EdgeInsets.fromLTRB(20, 0, 20, 8),
            child: Text('Distances are measured from here.', style: AppText.muted),
          ),
          for (final area in areas)
            ListTile(
              contentPadding: const EdgeInsets.symmetric(horizontal: 20),
              leading: const Icon(Icons.location_on_outlined, color: AppColors.teal),
              title: Text(area.name),
              trailing: area == currentArea.value
                  ? const Icon(Icons.check_rounded, color: AppColors.teal)
                  : null,
              onTap: () => Navigator.pop(context, area),
            ),
          const SizedBox(height: 8),
        ],
      ),
    ),
  );
  if (picked != null) currentArea.value = picked;
}
