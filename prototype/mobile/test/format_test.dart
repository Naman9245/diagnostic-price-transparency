import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ratecard/format.dart';
import 'package:ratecard/widgets/common.dart';

void main() {
  test('rupees are grouped the Indian way', () {
    expect(rupees(240), '₹240');
    expect(rupees(1450), '₹1,450');
    expect(rupees(12500), '₹12,500');
    expect(rupees(125000), '₹1,25,000');
    expect(rupees(10000000), '₹1,00,00,000');
  });

  test('slot times read like a clock', () {
    expect(clockTime('07:30'), '7:30 AM');
    expect(clockTime('12:00'), '12:00 PM');
    expect(clockTime('16:00'), '4:00 PM');
  });

  test('dates and distances', () {
    expect(shortDate(DateTime(2026, 9, 30)), 'Wed, 30 Sep');
    expect(longDate(DateTime(2026, 9, 12)), '12 Sep 2026');
    expect(km(0.34), '0.3 km');
    expect(km(14.1), '14 km');
  });

  test('phone numbers and weekdays', () {
    expect(phoneNumber('9876543210'), '+91 98765 43210');
    expect(weekdayNumber('Mon'), DateTime.monday);
    expect(weekdayNumber('Sun'), DateTime.sunday);
  });

  test('initials skip the Dr. and use the first and last names', () {
    expect(initials('Dr. Ananya Rao'), 'AR');
    expect(initials("Dr. Rohan D'Souza"), 'RD');
    expect(initials('Dr Meera Iyer'), 'MI');
    expect(initials('  priya   lakshmi menon '), 'PM');
    expect(initials('Ananya'), 'A');
    expect(initials('Drishti Rao'), 'DR', reason: 'a name starting "Dr" is not a title');
    expect(initials(''), '');
  });

  testWidgets('a rating shows one decimal place and a short count', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Rating(4, count: 2140)));
    expect(find.text('4.0'), findsOneWidget);
    expect(find.text(' (2.1K)'), findsOneWidget);
  });
}
