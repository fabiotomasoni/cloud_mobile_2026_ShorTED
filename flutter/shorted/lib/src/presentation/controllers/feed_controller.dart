import 'package:flutter/foundation.dart';

import '../../application/services/feed_service.dart';
import '../../domain/models/user_profile.dart';
import '../states/feed_state.dart';

class FeedController extends ChangeNotifier {
  FeedController(this._feedService, this._profile) : state = FeedState.initial();

  static const docsPerPage = 20;
  static const prefetchThreshold = 5;

  final FeedService _feedService;
  final UserProfile _profile;
  FeedState state;

  Future<void> loadNextPage() async {
    if (state.loading || !state.hasMore) return;
    state = state.copyWith(loading: true, clearError: true);
    notifyListeners();

    try {
      final pageItems = await _feedService.loadFeedPage(
        tags: _profile.selectedTags,
        page: state.page,
        docsPerPage: docsPerPage,
      );
      state = state.copyWith(
        snacks: [...state.snacks, ...pageItems],
        page: state.page + 1,
        hasMore: pageItems.length == docsPerPage,
      );
    } catch (error) {
      state = state.copyWith(error: error);
    } finally {
      state = state.copyWith(loading: false);
      notifyListeners();
    }
  }

  void onPageChanged(int index) {
    if (state.snacks.length - index <= prefetchThreshold) {
      loadNextPage();
    }
  }
}
