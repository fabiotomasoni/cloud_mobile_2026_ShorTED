import 'package:flutter/foundation.dart';

import '../../application/services/profile_service.dart';
import '../../domain/models/user_profile.dart';
import '../states/edit_tags_state.dart';

class EditTagsController extends ChangeNotifier {
  EditTagsController(this._profileService, this._profile)
      : state = EditTagsState.initial(_profile.selectedTags.toSet());

  final ProfileService _profileService;
  final UserProfile _profile;
  EditTagsState state;

  Future<void> loadTags() async {
    state = state.copyWith(loading: true, clearError: true);
    notifyListeners();

    try {
      final tags = await _profileService.loadAvailableTags();
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
      if (selected.length > 3) selected.remove(tag);
    } else {
      selected.add(tag);
    }
    state = state.copyWith(selectedTags: selected);
    notifyListeners();
  }

  UserProfile buildUpdatedProfile() {
    return _profileService.updateTags(_profile, state.selectedTags.toList());
  }
}
