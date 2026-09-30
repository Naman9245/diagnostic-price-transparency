import 'package:flutter/material.dart';

import '../format.dart';
import '../location.dart';
import '../session.dart';
import '../theme.dart';
import '../widgets/area_sheet.dart';
import '../widgets/common.dart';
import '../widgets/initials_avatar.dart';
import 'shell.dart';

/// The Profile tab: who's signed in, with shortcuts to their bookings, the
/// area prices are measured from, and signing out.
class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(automaticallyImplyLeading: false, title: const Text('Profile')),
      body: ValueListenableBuilder(
        valueListenable: currentUser,
        builder: (context, user, _) => user == null
            ? EmptyState(
                icon: Icons.person_outline_rounded,
                title: 'You’re not signed in',
                message: 'Sign in with your mobile number to book tests and doctors.',
                action: 'Sign in',
                onAction: () => ensureSignedIn(context),
              )
            : _Profile(user: user),
      ),
    );
  }
}

class _Profile extends StatelessWidget {
  const _Profile({required this.user});

  final User user;

  @override
  Widget build(BuildContext context) {
    final phone = phoneNumber(user.phone);
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
      children: [
        Center(
          child: InitialsAvatar(name: user.name ?? '', color: AppColors.teal, size: 88),
        ),
        const SizedBox(height: 14),
        // Someone who skipped giving a name is known by their number.
        Text(user.name ?? phone, textAlign: TextAlign.center, style: AppText.heading),
        if (user.name != null) Text(phone, textAlign: TextAlign.center, style: AppText.muted),
        const SizedBox(height: 24),
        _Row(
          icon: Icons.event_note_outlined,
          label: 'My bookings',
          onTap: () => shellTab.value = ShellTab.bookings,
        ),
        ValueListenableBuilder(
          valueListenable: currentArea,
          builder: (context, area, _) => _Row(
            icon: Icons.location_on_outlined,
            label: 'Change area',
            detail: area.name,
            onTap: () => pickArea(context),
          ),
        ),
        const _Row(
          icon: Icons.logout_rounded,
          label: 'Sign out',
          onTap: Session.signOut,
          destructive: true,
        ),
        const SizedBox(height: 20),
        const DemoNotice(
          text: 'A demo account: no texts are sent, and the server forgets it when it restarts.',
        ),
      ],
    );
  }
}

/// One line of the profile menu: an icon in a tinted circle, a label, and
/// what's set now, if anything.
class _Row extends StatelessWidget {
  const _Row({
    required this.icon,
    required this.label,
    required this.onTap,
    this.detail,
    this.destructive = false,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final String? detail;

  /// Coral rather than teal, and no arrow: signing out goes nowhere.
  final bool destructive;

  @override
  Widget build(BuildContext context) {
    final color = destructive ? AppColors.coral : AppColors.teal;
    return TapSurface(
      onTap: onTap,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(14))),
      scale: 0.98,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 10),
        child: Row(
          children: [
            CircleAvatar(
              radius: 20,
              backgroundColor: color.withValues(alpha: 0.12),
              child: Icon(icon, size: 20, color: color),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Text(
                label,
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: destructive ? color : AppColors.ink,
                ),
              ),
            ),
            if (detail != null) Text(detail!, style: AppText.muted),
            if (!destructive) const Icon(Icons.chevron_right_rounded, color: AppColors.slate),
          ],
        ),
      ),
    );
  }
}
