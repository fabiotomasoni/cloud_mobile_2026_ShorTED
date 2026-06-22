import 'package:flutter/material.dart';

import '../../application/services/feed_service.dart';
import '../../application/services/profile_service.dart';
import '../../domain/models/user_profile.dart';
import 'feed_screen.dart';
import 'profile_screen.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({
    super.key,
    required this.profile,
    required this.feedService,
    required this.profileService,
    required this.onProfileChanged,
  });

  final UserProfile profile;
  final FeedService feedService;
  final ProfileService profileService;
  final ValueChanged<UserProfile> onProfileChanged;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: [
          FeedScreen(profile: widget.profile, feedService: widget.feedService),
          ProfileScreen(
            profile: widget.profile,
            profileService: widget.profileService,
            onProfileChanged: widget.onProfileChanged,
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (index) => setState(() => _index = index),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.play_circle_outline), selectedIcon: Icon(Icons.play_circle), label: 'Feed'),
          NavigationDestination(icon: Icon(Icons.person_outline), selectedIcon: Icon(Icons.person), label: 'Profilo'),
        ],
      ),
    );
  }
}
