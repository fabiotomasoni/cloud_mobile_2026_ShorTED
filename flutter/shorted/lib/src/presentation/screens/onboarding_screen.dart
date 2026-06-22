import 'package:flutter/material.dart';

import '../../application/services/onboarding_service.dart';
import '../../domain/models/user_profile.dart';
import '../controllers/onboarding_controller.dart';
import '../states/onboarding_state.dart';

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({
    super.key,
    required this.onboardingService,
    required this.onComplete,
  });

  final OnboardingService onboardingService;
  final ValueChanged<UserProfile> onComplete;

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final _usernameController = TextEditingController();
  final _searchController = TextEditingController();
  late final OnboardingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = OnboardingController(widget.onboardingService)..loadTags();
  }

  @override
  void dispose() {
    _controller.dispose();
    _usernameController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  void _complete() {
    final profile = _controller.createProfile(_usernameController.text);
    widget.onComplete(profile);
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final state = _controller.state;
        return Scaffold(
          body: SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('ShorTED', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w900)),
                  const SizedBox(height: 8),
                  Text('Scegli almeno 3 interessi per costruire il tuo feed.', style: Theme.of(context).textTheme.bodyLarge),
                  const SizedBox(height: 24),
                  TextField(
                    controller: _usernameController,
                    decoration: const InputDecoration(labelText: 'Username', border: OutlineInputBorder()),
                    onChanged: (_) => setState(() {}),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _searchController,
                    decoration: const InputDecoration(labelText: 'Cerca tag', prefixIcon: Icon(Icons.search), border: OutlineInputBorder()),
                    onChanged: _controller.setSearchQuery,
                  ),
                  const SizedBox(height: 16),
                  Text('${state.selectedTags.length}/3 tag selezionati'),
                  const SizedBox(height: 8),
                  Expanded(child: _buildTagContent(state)),
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: _usernameController.text.trim().isNotEmpty && state.selectedTags.length >= 3 ? _complete : null,
                      child: const Text('Entra nel feed'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildTagContent(OnboardingState state) {
    if (state.loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (state.error != null) {
      return Center(child: Text('Errore caricamento tag: ${state.error}'));
    }

    return SingleChildScrollView(
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: state.filteredTags.map<Widget>((tag) {
          return FilterChip(
            label: Text(tag),
            selected: state.selectedTags.contains(tag),
            onSelected: (_) => _controller.toggleTag(tag),
          );
        }).toList(),
      ),
    );
  }
}
