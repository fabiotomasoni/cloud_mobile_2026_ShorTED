import 'package:flutter/material.dart';

import '../../domain/models/user_profile.dart';

class AppState {
  const AppState({
    required this.loading,
    required this.themeMode,
    this.profile,
  });

  final bool loading;
  final ThemeMode themeMode;
  final UserProfile? profile;

  bool get needsOnboarding => !loading && (profile == null || !profile!.isComplete);

  AppState copyWith({
    bool? loading,
    ThemeMode? themeMode,
    UserProfile? profile,
  }) {
    return AppState(
      loading: loading ?? this.loading,
      themeMode: themeMode ?? this.themeMode,
      profile: profile ?? this.profile,
    );
  }
}
