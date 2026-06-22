import 'package:flutter/material.dart';

import '../../application/services/feed_service.dart';
import '../../domain/models/user_profile.dart';
import '../controllers/feed_controller.dart';
import '../widgets/snack_feed_page.dart';
import 'snack_detail_page.dart';

class FeedScreen extends StatefulWidget {
  const FeedScreen({super.key, required this.profile, required this.feedService});

  final UserProfile profile;
  final FeedService feedService;

  @override
  State<FeedScreen> createState() => _FeedScreenState();
}

class _FeedScreenState extends State<FeedScreen> {
  late final FeedController _controller;

  @override
  void initState() {
    super.initState();
    _controller = FeedController(widget.feedService, widget.profile)..loadNextPage();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final state = _controller.state;
        if (state.isInitialLoading) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }

        if (state.hasInitialError) {
          return Scaffold(
            body: Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text('Errore caricamento feed', style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: 8),
                    Text(state.error.toString(), textAlign: TextAlign.center),
                    const SizedBox(height: 16),
                    FilledButton(onPressed: _controller.loadNextPage, child: const Text('Riprova')),
                  ],
                ),
              ),
            ),
          );
        }

        return PageView.builder(
          scrollDirection: Axis.vertical,
          itemCount: state.snacks.length,
          onPageChanged: _controller.onPageChanged,
          itemBuilder: (context, index) {
            return PageView(
              children: [
                SnackFeedPage(snack: state.snacks[index]),
                SnackDetailPage(snack: state.snacks[index]),
              ],
            );
          },
        );
      },
    );
  }
}
