import 'package:flutter/material.dart';

import '../../application/services/profile_service.dart';
import '../../domain/models/user_profile.dart';
import '../controllers/edit_tags_controller.dart';
import '../states/edit_tags_state.dart';

class EditTagsScreen extends StatefulWidget {
  const EditTagsScreen({
    super.key,
    required this.profile,
    required this.profileService,
    required this.onProfileChanged,
  });

  final UserProfile profile;
  final ProfileService profileService;
  final ValueChanged<UserProfile> onProfileChanged;

  @override
  State<EditTagsScreen> createState() => _EditTagsScreenState();
}

class _EditTagsScreenState extends State<EditTagsScreen> {
  final _searchController = TextEditingController();
  late final EditTagsController _controller;

  @override
  void initState() {
    super.initState();
    _controller = EditTagsController(widget.profileService, widget.profile)..loadTags();
  }

  @override
  void dispose() {
    _controller.dispose();
    _searchController.dispose();
    super.dispose();
  }

  void _save() {
    widget.onProfileChanged(_controller.buildUpdatedProfile());
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final state = _controller.state;
        return Scaffold(
          appBar: AppBar(title: const Text('Modifica interessi'), actions: [TextButton(onPressed: _save, child: const Text('Salva'))]),
          body: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                TextField(
                  controller: _searchController,
                  decoration: const InputDecoration(labelText: 'Cerca tag', prefixIcon: Icon(Icons.search), border: OutlineInputBorder()),
                  onChanged: _controller.setSearchQuery,
                ),
                const SizedBox(height: 12),
                Text('${state.selectedTags.length} tag selezionati. Minimo 3.'),
                const SizedBox(height: 12),
                Expanded(child: _buildTagContent(state)),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildTagContent(EditTagsState state) {
    if (state.loading) return const Center(child: CircularProgressIndicator());
    if (state.error != null) return Center(child: Text(state.error.toString()));

    return SingleChildScrollView(
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: state.filteredTags.map<Widget>((tag) {
          return FilterChip(label: Text(tag), selected: state.selectedTags.contains(tag), onSelected: (_) => _controller.toggleTag(tag));
        }).toList(),
      ),
    );
  }
}
