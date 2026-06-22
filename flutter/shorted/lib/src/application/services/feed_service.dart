import 'dart:math';

import '../../domain/models/snack.dart';
import '../../domain/repositories/snack_repository.dart';

class FeedService {
  const FeedService(this._snackRepository, {Random? random}) : _random = random;

  final SnackRepository _snackRepository;
  final Random? _random;

  Future<List<Snack>> loadFeedPage({
    required List<String> tags,
    required int page,
    required int docsPerPage,
  }) async {
    final snacks = await _snackRepository.getTalksByTags(tags: tags, page: page, docsPerPage: docsPerPage);
    snacks.shuffle(_random ?? Random());
    return snacks;
  }
}
