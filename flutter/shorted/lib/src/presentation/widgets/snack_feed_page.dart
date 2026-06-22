import 'package:flutter/material.dart';

import '../../domain/models/snack.dart';
import '../screens/video_player_screen.dart';
import 'glass_panel.dart';

class SnackFeedPage extends StatelessWidget {
  const SnackFeedPage({super.key, required this.snack});

  final Snack snack;

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        SnackVisualBackground(snack: snack),
        const IgnorePointer(
          child: DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Colors.black54, Colors.transparent, Colors.black87],
              ),
            ),
          ),
        ),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('ShorTED', style: Theme.of(context).textTheme.headlineSmall?.copyWith(color: Colors.white, fontWeight: FontWeight.w900)),
                    const Icon(Icons.swipe_left, color: Colors.white70),
                  ],
                ),
                const Spacer(),
                Text(
                  snack.aphorism.isNotEmpty ? snack.aphorism : snack.quote,
                  style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w900,
                        shadows: const [Shadow(blurRadius: 12, color: Colors.black)],
                      ),
                ),
                const SizedBox(height: 16),
                GlassPanel(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(snack.speaker, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
                      const SizedBox(height: 4),
                      Text(snack.talkTitle, style: const TextStyle(color: Colors.white70)),
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: snack.tags.take(4).map((tag) => Chip(label: Text(tag), visualDensity: VisualDensity.compact)).toList(),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: () => showSnackVideoPlayer(context, snack),
                    icon: const Icon(Icons.play_arrow),
                    label: const Text('Play talk'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class SnackVisualBackground extends StatelessWidget {
  const SnackVisualBackground({super.key, required this.snack});

  final Snack snack;

  @override
  Widget build(BuildContext context) {
    final thumbnailUrl = snack.bestThumbnailUrl;
    return Stack(
      fit: StackFit.expand,
      children: [
        const DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xff080808), Color(0xff2a0d0a), Color(0xff101010)],
            ),
          ),
        ),
        if (thumbnailUrl.isNotEmpty)
          Image.network(
            thumbnailUrl,
            fit: BoxFit.cover,
            errorBuilder: (_, _, _) => const SizedBox.shrink(),
          ),
        DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [
                Colors.black.withValues(alpha: 0.24),
                Colors.black.withValues(alpha: 0.22),
                Colors.black.withValues(alpha: 0.82),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
