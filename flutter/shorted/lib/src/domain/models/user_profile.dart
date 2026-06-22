import 'package:flutter/material.dart';

class UserProfile {
  const UserProfile({
    required this.username,
    required this.selectedTags,
    required this.themeMode,
  });

  final String username;
  final List<String> selectedTags;
  final ThemeMode themeMode;

  bool get isComplete => username.trim().isNotEmpty && selectedTags.length >= 3;

  UserProfile copyWith({
    String? username,
    List<String>? selectedTags,
    ThemeMode? themeMode,
  }) {
    return UserProfile(
      username: username ?? this.username,
      selectedTags: selectedTags ?? this.selectedTags,
      themeMode: themeMode ?? this.themeMode,
    );
  }
}
