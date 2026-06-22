import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shorted/src/app.dart';

void main() {
  testWidgets('shows ShorTED onboarding shell', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});

    await tester.pumpWidget(const ShorTEDApp());
    await tester.pumpAndSettle();

    expect(find.text('ShorTED'), findsOneWidget);
    expect(find.text('Entra nel feed'), findsOneWidget);
  });
}
