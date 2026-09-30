import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ratecard/screens/login_screen.dart';
import 'package:ratecard/session.dart';
import 'package:ratecard/theme.dart';

void main() {
  testWidgets('Send code turns on only for a valid mobile number', (tester) async {
    await tester.pumpWidget(MaterialApp(theme: buildTheme(), home: const LoginScreen()));
    final field = find.byType(TextField);
    bool sendCodeEnabled() =>
        tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Send code')).enabled;
    Future<void> type(String text) async {
      await tester.enterText(field, text);
      await tester.pump();
    }

    // The start page: +91 is fixed, and signing in can be skipped.
    expect(find.text('+91'), findsOneWidget);
    expect(find.text('Skip for now'), findsOneWidget);
    expect(sendCodeEnabled(), isFalse);

    await type('98765');
    expect(sendCodeEnabled(), isFalse, reason: 'too short');

    await type('5876543210');
    expect(sendCodeEnabled(), isFalse, reason: 'Indian mobile numbers start 6 to 9');

    await type('');
    await type('98765-43210 99');
    expect(tester.widget<TextField>(field).controller!.text, '9876543210');
    expect(sendCodeEnabled(), isTrue);
  });

  testWidgets('a sign-in counts even if the name step is left with Back', (tester) async {
    addTearDown(() => currentUser.value = null);
    await tester.pumpWidget(
      MaterialApp(home: const Text('booking'), routes: {'/login': (_) => const Text('sign in')}),
    );
    final signedIn = ensureSignedIn(tester.element(find.text('booking')));
    await tester.pumpAndSettle();

    currentUser.value = User.fromJson({'phone': '9876543210', 'name': null}); // code accepted
    tester.state<NavigatorState>(find.byType(Navigator)).pop(); // Back, not Continue
    await tester.pumpAndSettle();
    expect(await signedIn, isTrue);
  });
}
