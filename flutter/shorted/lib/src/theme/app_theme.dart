import 'package:flutter/material.dart';

class AppTheme {
  static const _red = Color(0xffff5542);
  static const _darkBackground = Color(0xff131313);

  static ThemeData get dark => ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: _red,
          brightness: Brightness.dark,
          surface: _darkBackground,
        ),
        scaffoldBackgroundColor: _darkBackground,
        useMaterial3: true,
      );

  static ThemeData get light => ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: _red),
        useMaterial3: true,
      );
}
