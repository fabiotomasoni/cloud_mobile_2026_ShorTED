import 'package:flutter/material.dart';

import '../../domain/models/snack.dart';
import 'glass_panel.dart';
import 'ted_embed_background.dart';

class SnackFeedPage extends StatelessWidget {
  const SnackFeedPage({super.key, required this.snack});

  final Snack snack;

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        TedEmbedBackground(snack: snack),
        const DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Colors.black54, Colors.transparent, Colors.black87],
            ),
          ),
        ),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 96),
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
              ],
            ),
          ),
        ),
      ],
    );
  }
}
