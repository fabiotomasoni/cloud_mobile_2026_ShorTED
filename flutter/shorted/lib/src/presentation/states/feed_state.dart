import '../../domain/models/snack.dart';

class FeedState {
  const FeedState({
    required this.snacks,
    required this.page,
    required this.loading,
    required this.hasMore,
    this.error,
  });

  factory FeedState.initial() {
    return const FeedState(snacks: [], page: 1, loading: false, hasMore: true);
  }

  final List<Snack> snacks;
  final int page;
  final bool loading;
  final bool hasMore;
  final Object? error;

  bool get isInitialLoading => snacks.isEmpty && loading;
  bool get hasInitialError => snacks.isEmpty && error != null;

  FeedState copyWith({
    List<Snack>? snacks,
    int? page,
    bool? loading,
    bool? hasMore,
    Object? error,
    bool clearError = false,
  }) {
    return FeedState(
      snacks: snacks ?? this.snacks,
      page: page ?? this.page,
      loading: loading ?? this.loading,
      hasMore: hasMore ?? this.hasMore,
      error: clearError ? null : error ?? this.error,
    );
  }
}
