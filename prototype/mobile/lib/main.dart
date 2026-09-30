import 'package:flutter/material.dart';

import 'models.dart';
import 'screens/confirmation_screen.dart';
import 'screens/doctor_screen.dart';
import 'screens/doctors_screen.dart';
import 'screens/hospital_screen.dart';
import 'screens/labs_screen.dart';
import 'screens/login_screen.dart';
import 'screens/results_screen.dart';
import 'screens/search_screen.dart';
import 'screens/shell.dart';
import 'screens/tests_screen.dart';
import 'session.dart';
import 'theme.dart';
import 'widgets/common.dart';

Future<void> main() async {
  // The saved sign-in decides the first page, so it's read before the app starts.
  WidgetsFlutterBinding.ensureInitialized();
  await Session.restore();
  runApp(const RateCardApp());
}

class RateCardApp extends StatelessWidget {
  const RateCardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'RateCard',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      onGenerateRoute: _route,
      onGenerateInitialRoutes: _initialRoutes,
      onUnknownRoute: _notFound,
    );
  }
}

/// Every page has an address, so the web build can open any page from a
/// link, for example http://localhost:5500/#/test/cbc
///
///     /                                 the tabs (add ?tab=doctors, bookings or profile)
///     /login                            sign in
///     /search                           search for a test
///     /tests                            every test
///     /labs                             every lab near you
///     /test/<test id>                   labs that offer a test
///     /hospital/<id>?test=<test id>     one lab
///     /doctors?specialty=<id>           doctors near you, optionally of one specialty
///     /doctor/<id>                      one doctor
///     /booked                           booking confirmed (needs a Booking)
Route<Object?>? _route(RouteSettings settings) {
  final uri = Uri.parse(settings.name ?? '/');
  final Widget? page = switch (uri.pathSegments) {
    [] => MainShell(initialTab: _tabNamed(uri.queryParameters['tab'])),
    ['login'] => const LoginScreen(),
    ['search'] => const SearchScreen(),
    ['tests'] => const TestsScreen(),
    ['labs'] => const LabsScreen(),
    ['test', final testId] => ResultsScreen(testId: testId),
    ['hospital', final id] => HospitalScreen(
      hospitalId: id,
      testId: uri.queryParameters['test'] ?? 'cbc',
    ),
    ['doctors'] => DoctorsScreen(specialty: uri.queryParameters['specialty']),
    ['doctor', final id] => DoctorScreen(doctorId: id),
    ['booked'] when settings.arguments is Booking => ConfirmationScreen(
      booking: settings.arguments as Booking,
    ),
    _ => null,
  };
  if (page == null) return null;
  return MaterialPageRoute(settings: settings, builder: (_) => page);
}

/// For an address typed or edited in the browser that leads nowhere.
Route<Object?> _notFound(RouteSettings settings) => MaterialPageRoute(
  settings: settings,
  builder: (_) => Scaffold(
    appBar: pageBar(),
    body: const EmptyState(
      icon: Icons.link_off_rounded,
      title: 'Page not found',
      message: 'There’s nothing at this address. Go back to keep browsing.',
    ),
  ),
);

ShellTab? _tabNamed(String? name) => ShellTab.values.where((tab) => tab.name == name).firstOrNull;

/// The app starts on the sign-in page until you've signed in once. A link
/// straight to any other page opens it directly, because browsing needs no
/// account, with the tabs underneath so the back button has somewhere to go.
List<Route<dynamic>> _initialRoutes(String name) {
  Route<Object?> at(String name) => _route(RouteSettings(name: name))!;
  if (name == '/' && currentUser.value == null) return [at('/login')];
  final page = _route(RouteSettings(name: name));
  if (page == null) return [at('/')];
  if (Uri.parse(name).pathSegments.isEmpty) return [page]; // one of the tabs
  return [at('/'), page];
}
