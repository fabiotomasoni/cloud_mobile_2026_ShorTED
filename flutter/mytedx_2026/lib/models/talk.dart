class Talk {
  final String id;
  final String title;
  final String details;
  final String mainSpeaker;
  final String url;
  final List<String> keyPhrases;

  Talk.fromJSON(Map<String, dynamic> jsonMap)
      : id = jsonMap['_id'] ?? jsonMap['id'] ?? jsonMap['related_id'] ?? "",
        title = jsonMap['title'] ?? "",
        details = jsonMap['description'] ?? jsonMap['details'] ?? _buildDetails(jsonMap),
        mainSpeaker = jsonMap['speakers'] ?? jsonMap['presenterDisplayName'] ?? "",
        url = jsonMap['url'] ?? (jsonMap['slug'] != null ? "https://www.ted.com/talks/${jsonMap['slug']}" : ""),
        keyPhrases = (jsonMap['comprehend_analysis'] != null && jsonMap['comprehend_analysis']['KeyPhrases'] != null)
            ? (jsonMap['comprehend_analysis']['KeyPhrases'] as List<dynamic>)
                .map((e) => e.toString())
                .toList()
            : [];

  static String _buildDetails(Map<String, dynamic> jsonMap) {
    final views = jsonMap['viewedCount'];
    final duration = jsonMap['duration'];
    List<String> parts = [];
    if (views != null) {
      parts.add("Views: $views");
    }
    if (duration != null) {
      final minutes = int.tryParse(duration.toString()) != null
          ? (int.parse(duration.toString()) / 60).floor()
          : 0;
      final seconds = int.tryParse(duration.toString()) != null
          ? int.parse(duration.toString()) % 60
          : 0;
      parts.add("Duration: ${minutes}m ${seconds}s");
    }
    return parts.isEmpty ? "No details available." : parts.join(" | ");
  }
}