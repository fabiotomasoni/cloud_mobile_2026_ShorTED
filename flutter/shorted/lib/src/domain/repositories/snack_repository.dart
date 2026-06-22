import '../models/snack.dart';

abstract class SnackRepository {
  Future<List<String>> getAllTags();

  Future<List<Snack>> getTalksByTags({
    required List<String> tags,
    required int page,
    required int docsPerPage,
  });
}
