import 'package:flutter/material.dart';

import '../theme.dart';
import '../widgets/common.dart';
import '../widgets/pressable.dart';
import 'bookings_screen.dart';
import 'doctors_screen.dart';
import 'home_screen.dart';
import 'profile_screen.dart';

/// The four tabs along the bottom: an outline icon, a filled one for when the
/// tab is showing, and a label.
enum ShellTab {
  home(Icons.home_outlined, Icons.home_rounded, 'Home'),
  doctors(Icons.medical_services_outlined, Icons.medical_services_rounded, 'Doctors'),
  bookings(Icons.event_note_outlined, Icons.event_note_rounded, 'Bookings'),
  profile(Icons.person_outline_rounded, Icons.person_rounded, 'Profile');

  const ShellTab(this.icon, this.activeIcon, this.label);

  final IconData icon, activeIcon;
  final String label;
}

/// Which tab is showing. Other screens change it: the booking confirmation,
/// for example, jumps to My bookings.
final shellTab = ValueNotifier<ShellTab>(ShellTab.home);

/// The app's frame: four tabs along the bottom, with a round search button
/// raised in the middle.
class MainShell extends StatefulWidget {
  const MainShell({super.key, this.initialTab});

  final ShellTab? initialTab;

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  // Tabs are built the first time they're opened, so the app starts with one
  // screen's requests rather than four.
  final _opened = <ShellTab>{};

  // Bumped each time My bookings opens, so it reloads with any new booking.
  int _bookingsVersion = 0;

  @override
  void initState() {
    super.initState();
    if (widget.initialTab != null) shellTab.value = widget.initialTab!;
    _opened.add(shellTab.value);
    shellTab.addListener(_tabChanged);
  }

  @override
  void dispose() {
    shellTab.removeListener(_tabChanged);
    super.dispose();
  }

  void _tabChanged() => setState(() {
    _opened.add(shellTab.value);
    if (shellTab.value == ShellTab.bookings) _bookingsVersion++;
  });

  Widget _screen(ShellTab tab) => switch (tab) {
    ShellTab.home => const HomeScreen(),
    ShellTab.doctors => const DoctorsScreen(),
    ShellTab.bookings => BookingsScreen(key: ValueKey(_bookingsVersion)),
    ShellTab.profile => const ProfileScreen(),
  };

  @override
  Widget build(BuildContext context) {
    final current = shellTab.value;
    return PopScope(
      // Back on another tab goes to Home first, as in most apps.
      canPop: current == ShellTab.home,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) shellTab.value = ShellTab.home;
      },
      child: Scaffold(
        // Every opened tab stays alive, so switching back keeps its scroll.
        body: IndexedStack(
          index: current.index,
          children: [
            for (final tab in ShellTab.values)
              _opened.contains(tab) ? _screen(tab) : const SizedBox.shrink(),
          ],
        ),
        floatingActionButtonLocation: FloatingActionButtonLocation.centerDocked,
        floatingActionButton: Pressable(
          scale: 0.9,
          child: FloatingActionButton(
            tooltip: 'Search tests',
            elevation: 3,
            shape: const CircleBorder(side: BorderSide(color: Colors.white, width: 4)),
            onPressed: () => Navigator.pushNamed(context, '/search'),
            child: const Icon(Icons.search_rounded, size: 26),
          ),
        ),
        bottomNavigationBar: _TabBar(current: current, onSelect: (tab) => shellTab.value = tab),
      ),
    );
  }
}

class _TabBar extends StatelessWidget {
  const _TabBar({required this.current, required this.onSelect});

  final ShellTab current;
  final ValueChanged<ShellTab> onSelect;

  @override
  Widget build(BuildContext context) {
    final [home, doctors, bookings, profile] = ShellTab.values.map(_item).toList();
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 16,
            offset: const Offset(0, -4),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 64,
          // A gap in the middle leaves room for the search button.
          child: Row(children: [home, doctors, const SizedBox(width: 72), bookings, profile]),
        ),
      ),
    );
  }

  Widget _item(ShellTab tab) {
    final selected = tab == current;
    final color = selected ? AppColors.teal : AppColors.slate;
    return Expanded(
      child: TapSurface(
        onTap: () => onSelect(tab),
        selected: selected,
        shape: const RoundedRectangleBorder(),
        scale: 0.9,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            AnimatedScale(
              scale: selected ? 1.12 : 1,
              duration: const Duration(milliseconds: 200),
              curve: Curves.easeOut,
              child: Icon(selected ? tab.activeIcon : tab.icon, color: color, size: 24),
            ),
            const SizedBox(height: 3),
            Text(
              tab.label,
              style: TextStyle(
                fontSize: 11.5,
                fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                color: color,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
