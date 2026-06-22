import 'package:flutter/material.dart';

import '../../application/services/profile_service.dart';
import '../../domain/models/user_profile.dart';
import 'edit_tags_screen.dart';
import 'settings_screen.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({
    super.key,
    required this.profile,
    required this.profileService,
    required this.onProfileChanged,
  });

  final UserProfile profile;
  final ProfileService profileService;
  final ValueChanged<UserProfile> onProfileChanged;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Profilo'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
              builder: (_) => SettingsScreen(
                profile: profile,
                profileService: profileService,
                onProfileChanged: onProfileChanged,
              ),
            )),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                children: [
                  CircleAvatar(radius: 42, child: Text(profile.username.characters.first.toUpperCase(), style: const TextStyle(fontSize: 32))),
                  const SizedBox(height: 16),
                  Text(profile.username, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  const Text('Profilo locale V1'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Interessi', style: Theme.of(context).textTheme.titleLarge),
              TextButton(
                onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
                  builder: (_) => EditTagsScreen(
                    profile: profile,
                    profileService: profileService,
                    onProfileChanged: onProfileChanged,
                  ),
                )),
                child: const Text('Modifica'),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Wrap(spacing: 8, runSpacing: 8, children: profile.selectedTags.map((tag) => Chip(label: Text(tag))).toList()),
        ],
      ),
    );
  }
}
