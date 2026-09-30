import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ratecard/widgets/pressable.dart';

void main() {
  Future<double Function()> pumpButton(WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Center(
          child: Pressable(child: SizedBox(width: 120, height: 48, child: Text('Book'))),
        ),
      ),
    );
    return () => tester.widget<AnimatedScale>(find.byType(AnimatedScale)).scale;
  }

  testWidgets('shrinks while pressed and springs back on release', (tester) async {
    final scale = await pumpButton(tester);
    expect(scale(), 1);

    final press = await tester.startGesture(tester.getCenter(find.text('Book')));
    await tester.pump();
    expect(scale(), 0.95);

    await press.up();
    await tester.pumpAndSettle();
    expect(scale(), 1);
  });

  testWidgets('lets go when the finger moves like a scroll', (tester) async {
    final scale = await pumpButton(tester);
    final press = await tester.startGesture(tester.getCenter(find.text('Book')));
    await tester.pump();

    await press.moveBy(const Offset(0, 40));
    await tester.pumpAndSettle();
    expect(scale(), 1);
    await press.up();
  });
}
