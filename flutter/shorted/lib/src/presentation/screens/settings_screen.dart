import 'package:flutter/material.dart';

import '../../application/services/profile_service.dart';
import '../../domain/models/user_profile.dart';
import '../controllers/settings_controller.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({
    super.key,
    required this.profile,
    required this.profileService,
    required this.onProfileChanged,
  });

  final UserProfile profile;
  final ProfileService profileService;
  final ValueChanged<UserProfile> onProfileChanged;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _usernameController;
  late final SettingsController _controller;

  @override
  void initState() {
    super.initState();
    _usernameController = TextEditingController(text: widget.profile.username);
    _controller = SettingsController(widget.profileService, widget.profile);
  }

  @override
  void dispose() {
    _controller.dispose();
    _usernameController.dispose();
    super.dispose();
  }

  void _save() {
    widget.onProfileChanged(_controller.buildUpdatedProfile(_usernameController.text));
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        return Scaffold(
          appBar: AppBar(title: const Text('Impostazioni'), actions: [TextButton(onPressed: _save, child: const Text('Salva'))]),
          body: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              TextField(controller: _usernameController, decoration: const InputDecoration(labelText: 'Username', border: OutlineInputBorder())),
              const SizedBox(height: 24),
              SegmentedButton<ThemeMode>(
                segments: const [
                  ButtonSegment(value: ThemeMode.dark, label: Text('Dark'), icon: Icon(Icons.dark_mode)),
                  ButtonSegment(value: ThemeMode.light, label: Text('Light'), icon: Icon(Icons.light_mode)),
                ],
                selected: {_controller.themeMode},
                onSelectionChanged: (value) => _controller.setThemeMode(value.first),
              ),
            ],
          ),
        );
      },
    );
  }
}
