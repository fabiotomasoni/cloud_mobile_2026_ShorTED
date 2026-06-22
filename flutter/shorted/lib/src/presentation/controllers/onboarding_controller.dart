import 'package:flutter/foundation.dart';

import '../../application/services/onboarding_service.dart';
import '../../domain/models/user_profile.dart';
import '../states/onboarding_state.dart';

class OnboardingController extends ChangeNotifier {
  OnboardingController(this._onboardingService) : state = OnboardingState.initial();

  final OnboardingService _onboardingService;
  OnboardingState state;

  Future<void> loadTags() async {
    state = state.copyWith(loading: true, clearError: true);
    notifyListeners();

    try {
      final tags = await _onboardingService.loadAvailableTags();
      state = state.copyWith(availableTags: tags, loading: false);
    } catch (error) {
      state = state.copyWith(error: error, loading: false);
    }
    notifyListeners();
  }

  void setSearchQuery(String query) {
    state = state.copyWith(searchQuery: query);
    notifyListeners();
  }

  void toggleTag(String tag) {
    final selected = {...state.selectedTags};
    if (selected.contains(tag)) {
      selected.remove(tag);
    } else {
      selected.add(tag);
    }
    state = state.copyWith(selectedTags: selected);
    notifyListeners();
  }

  UserProfile createProfile(String username) {
    return _onboardingService.createProfile(username: username, selectedTags: state.selectedTags.toList());
  }
}
