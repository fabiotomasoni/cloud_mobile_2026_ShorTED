class EditTagsState {
  const EditTagsState({
    required this.availableTags,
    required this.selectedTags,
    required this.loading,
    required this.searchQuery,
    this.error,
  });

  factory EditTagsState.initial(Set<String> selectedTags) {
    return EditTagsState(
      availableTags: const [],
      selectedTags: selectedTags,
      loading: true,
      searchQuery: '',
    );
  }

  final List<String> availableTags;
  final Set<String> selectedTags;
  final bool loading;
  final String searchQuery;
  final Object? error;

  List<String> get filteredTags {
    final query = searchQuery.toLowerCase().trim();
    return availableTags.where((tag) => query.isEmpty || tag.toLowerCase().contains(query)).take(180).toList();
  }

  EditTagsState copyWith({
    List<String>? availableTags,
    Set<String>? selectedTags,
    bool? loading,
    String? searchQuery,
    Object? error,
    bool clearError = false,
  }) {
    return EditTagsState(
      availableTags: availableTags ?? this.availableTags,
      selectedTags: selectedTags ?? this.selectedTags,
      loading: loading ?? this.loading,
      searchQuery: searchQuery ?? this.searchQuery,
      error: clearError ? null : error ?? this.error,
    );
  }
}
