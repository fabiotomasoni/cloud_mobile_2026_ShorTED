import 'package:flutter/material.dart';

import '../../domain/models/user_profile.dart';
import '../../domain/repositories/profile_repository.dart';
import '../../domain/repositories/snack_repository.dart';

class ProfileService {
  const ProfileService(this._profileRepository, this._snackRepository);

  final ProfileRepository _profileRepository;
  final SnackRepository _snackRepository;

  Future<UserProfile?> loadProfile() => _profileRepository.loadProfile();

  Future<void> saveProfile(UserProfile profile) => _profileRepository.saveProfile(profile);

  Future<List<String>> loadAvailableTags() => _snackRepository.getAllTags();

  UserProfile updateUsername(UserProfile profile, String username) {
    final trimmed = username.trim();
    if (trimmed.isEmpty) {
      throw ArgumentError('Username is required.');
    }
    return profile.copyWith(username: trimmed);
  }

  UserProfile updateTheme(UserProfile profile, ThemeMode themeMode) {
    return profile.copyWith(themeMode: themeMode);
  }

  UserProfile updateTags(UserProfile profile, List<String> tags) {
    if (tags.length < 3) {
      throw ArgumentError('At least 3 tags are required.');
    }
    return profile.copyWith(selectedTags: tags);
  }
}
