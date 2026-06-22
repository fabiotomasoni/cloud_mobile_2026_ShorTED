import 'package:flutter/material.dart';

import '../../domain/models/user_profile.dart';
import '../../domain/repositories/snack_repository.dart';

class OnboardingService {
  const OnboardingService(this._snackRepository);

  final SnackRepository _snackRepository;

  Future<List<String>> loadAvailableTags() => _snackRepository.getAllTags();

  UserProfile createProfile({
    required String username,
    required List<String> selectedTags,
    ThemeMode themeMode = ThemeMode.dark,
  }) {
    final trimmedUsername = username.trim();
    if (trimmedUsername.isEmpty) {
      throw ArgumentError('Username is required.');
    }
    if (selectedTags.length < 3) {
      throw ArgumentError('At least 3 tags are required.');
    }

    return UserProfile(username: trimmedUsername, selectedTags: selectedTags, themeMode: themeMode);
  }
}
