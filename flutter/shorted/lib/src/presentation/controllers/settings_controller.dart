import 'package:flutter/material.dart';

import '../../application/services/profile_service.dart';
import '../../domain/models/user_profile.dart';

class SettingsController extends ChangeNotifier {
  SettingsController(this._profileService, this._profile) : themeMode = _profile.themeMode;

  final ProfileService _profileService;
  final UserProfile _profile;
  ThemeMode themeMode;

  void setThemeMode(ThemeMode value) {
    themeMode = value;
    notifyListeners();
  }

  UserProfile buildUpdatedProfile(String username) {
    final withUsername = _profileService.updateUsername(_profile, username);
    return _profileService.updateTheme(withUsername, themeMode);
  }
}
