import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../domain/models/snack.dart';
import '../widgets/glass_panel.dart';

class SnackDetailPage extends StatelessWidget {
  const SnackDetailPage({super.key, required this.snack});

  final Snack snack;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          Positioned.fill(child: SnackDetailBackground(snack: snack)),
          const Positioned.fill(child: ColoredBox(color: Colors.black87)),
          SafeArea(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 110),
              children: [
                Row(
                  children: [
                    const Icon(Icons.swipe_right, color: Colors.white70),
                    const SizedBox(width: 8),
                    Text('Feed', style: Theme.of(context).textTheme.labelLarge?.copyWith(color: Colors.white70)),
                  ],
                ),
                const SizedBox(height: 28),
                Wrap(spacing: 8, runSpacing: 8, children: snack.tags.map((tag) => Chip(label: Text(tag))).toList()),
                const SizedBox(height: 20),
                Text(snack.talkTitle, style: Theme.of(context).textTheme.headlineMedium?.copyWith(color: Colors.white, fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                Text(snack.speaker, style: Theme.of(context).textTheme.titleMedium?.copyWith(color: Colors.white70)),
                const SizedBox(height: 24),
                GlassPanel(child: Text('"${snack.quote}"', style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.w800, height: 1.2))),
                const SizedBox(height: 24),
                Text('Why this matters', style: Theme.of(context).textTheme.titleLarge?.copyWith(color: Theme.of(context).colorScheme.primary, fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                GlassPanel(child: Text(snack.motivationalText, style: const TextStyle(color: Colors.white70, fontSize: 16, height: 1.45))),
                const SizedBox(height: 24),
                Text(snack.aphorism, textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleLarge?.copyWith(color: Colors.white, fontWeight: FontWeight.bold)),
                const SizedBox(height: 24),
                FilledButton.icon(
                  onPressed: () => _openTedTalk(context),
                  icon: const Icon(Icons.open_in_new),
                  label: const Text('Open TED Talk'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _openTedTalk(BuildContext context) async {
    final uri = Uri.tryParse(snack.talkUrl);
    if (uri == null) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('TED link non valido')));
      }
      return;
    }

    final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!opened && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Impossibile aprire il link TED')));
    }
  }
}

class SnackDetailBackground extends StatelessWidget {
  const SnackDetailBackground({super.key, required this.snack});

  final Snack snack;

  @override
  Widget build(BuildContext context) {
    final thumbnailUrl = snack.bestThumbnailUrl;
    if (thumbnailUrl.isEmpty) {
      return const DecoratedBox(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xff080808), Color(0xff2a0d0a), Color(0xff101010)],
          ),
        ),
      );
    }
    return Image.network(
      thumbnailUrl,
      fit: BoxFit.cover,
      errorBuilder: (_, _, _) => const SizedBox.shrink(),
    );
  }
}
