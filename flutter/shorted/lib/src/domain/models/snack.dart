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
    required this.embedUrl,
    required this.thumbnailUrl,
    required this.thumbnailUrlHd,
    required this.thumbnailUrlFullHd,
    required this.hlsUrl,
    required this.mp4Url,
    required this.mediaExtractedAt,
    required this.mediaExtractionVersion,
    required this.mediaExtractionStatus,
    required this.mediaExtractionError,
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
  final String embedUrl;
  final String thumbnailUrl;
  final String thumbnailUrlHd;
  final String thumbnailUrlFullHd;
  final String hlsUrl;
  final String mp4Url;
  final String mediaExtractedAt;
  final String mediaExtractionVersion;
  final String mediaExtractionStatus;
  final String mediaExtractionError;
  final String language;
  final String aiPipelineVersion;
  final String sourceHash;
  final String createdAt;

  String get bestThumbnailUrl {
    if (thumbnailUrlFullHd.isNotEmpty) return thumbnailUrlFullHd;
    if (thumbnailUrlHd.isNotEmpty) return thumbnailUrlHd;
    return thumbnailUrl;
  }

  Uri? get mediaUri {
    if (hlsUrl.isNotEmpty) return Uri.tryParse(hlsUrl);
    if (mp4Url.isNotEmpty) return Uri.tryParse(mp4Url);
    return null;
  }
}
