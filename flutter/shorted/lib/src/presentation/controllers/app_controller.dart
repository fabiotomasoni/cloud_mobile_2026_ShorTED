import 'package:flutter/material.dart';

import '../../application/services/profile_service.dart';
import '../../domain/models/user_profile.dart';
import '../states/app_state.dart';

class AppController extends ChangeNotifier {
  AppController(this._profileService)
      : state = const AppState(loading: true, themeMode: ThemeMode.dark);

  final ProfileService _profileService;
  AppState state;

  Future<void> initialize() async {
    final profile = await _profileService.loadProfile();
    state = AppState(
      loading: false,
      profile: profile,
      themeMode: profile?.themeMode ?? ThemeMode.dark,
    );
    notifyListeners();
  }

  Future<void> saveProfile(UserProfile profile) async {
    await _profileService.saveProfile(profile);
    state = AppState(loading: false, profile: profile, themeMode: profile.themeMode);
    notifyListeners();
  }
}
