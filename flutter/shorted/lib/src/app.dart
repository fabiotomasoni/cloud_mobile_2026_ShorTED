import 'package:flutter/material.dart';

import 'app_dependencies.dart';
import 'presentation/controllers/app_controller.dart';
import 'presentation/screens/home_shell.dart';
import 'presentation/screens/onboarding_screen.dart';
import 'presentation/screens/splash_screen.dart';
import 'presentation/states/app_state.dart';
import 'theme/app_theme.dart';

class ShorTEDApp extends StatefulWidget {
  const ShorTEDApp({super.key});

  @override
  State<ShorTEDApp> createState() => _ShorTEDAppState();
}

class _ShorTEDAppState extends State<ShorTEDApp> {
  late final AppDependencies _dependencies;
  late final AppController _appController;

  @override
  void initState() {
    super.initState();
    _dependencies = AppDependencies();
    _appController = AppController(_dependencies.profileService)..initialize();
  }

  @override
  void dispose() {
    _appController.dispose();
    _dependencies.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _appController,
      builder: (context, _) {
        final state = _appController.state;
        return MaterialApp(
          title: 'ShorTED',
          debugShowCheckedModeBanner: false,
          themeMode: state.themeMode,
          theme: AppTheme.light,
          darkTheme: AppTheme.dark,
          home: _buildHome(state),
        );
      },
    );
  }

  Widget _buildHome(AppState state) {
    if (state.loading) {
      return const SplashScreen();
    }

    if (state.needsOnboarding) {
      return OnboardingScreen(
        onboardingService: _dependencies.onboardingService,
        onComplete: _appController.saveProfile,
      );
    }

    return HomeShell(
      profile: state.profile!,
      feedService: _dependencies.feedService,
      profileService: _dependencies.profileService,
      onProfileChanged: _appController.saveProfile,
    );
  }
}
