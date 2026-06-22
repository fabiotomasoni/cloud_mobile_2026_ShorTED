class Snack {
  const Snack({
    required this.id,
    required this.segmentId,
    required this.talkId,
    required this.talkSlug,
    required this.speaker,
    required this.talkTitle,
    required this.topic,
    required this.quote,
    required this.motivationalText,
    required this.aphorism,
    required this.tags,
    required this.score,
    required this.startTime,
    required this.endTime,
    required this.talkUrl,
    required this.language,
    required this.aiPipelineVersion,
    required this.sourceHash,
    required this.createdAt,
  });

  final String id;
  final String segmentId;
  final String talkId;
  final String talkSlug;
  final String speaker;
  final String talkTitle;
  final String topic;
  final String quote;
  final String motivationalText;
  final String aphorism;
  final List<String> tags;
  final double score;
  final int startTime;
  final int endTime;
  final String talkUrl;
  final String language;
  final String aiPipelineVersion;
  final String sourceHash;
  final String createdAt;

  Uri get embedUri {
    final parsed = Uri.tryParse(talkUrl);
    if (parsed != null && parsed.host == 'www.ted.com') {
      return parsed.replace(host: 'embed.ted.com');
    }
    if (talkSlug.isNotEmpty) {
      return Uri.https('embed.ted.com', '/talks/$talkSlug', {'t': startTime.toString()});
    }
    return Uri.parse('about:blank');
  }
}
