import 'package:http/http.dart' as http;

import 'application/services/feed_service.dart';
import 'application/services/onboarding_service.dart';
import 'application/services/profile_service.dart';
import 'data/datasources/profile_local_data_source.dart';
import 'data/datasources/shorted_remote_data_source.dart';
import 'data/repositories/profile_repository_impl.dart';
import 'data/repositories/snack_repository_impl.dart';

class AppDependencies {
  AppDependencies() {
    _httpClient = http.Client();
    _remoteDataSource = ShortedRemoteDataSource(client: _httpClient);
    _profileLocalDataSource = ProfileLocalDataSource();
    _snackRepository = SnackRepositoryImpl(_remoteDataSource);
    _profileRepository = ProfileRepositoryImpl(_profileLocalDataSource);
    feedService = FeedService(_snackRepository);
    onboardingService = OnboardingService(_snackRepository);
    profileService = ProfileService(_profileRepository, _snackRepository);
  }

  late final http.Client _httpClient;
  late final ShortedRemoteDataSource _remoteDataSource;
  late final ProfileLocalDataSource _profileLocalDataSource;
  late final SnackRepositoryImpl _snackRepository;
  late final ProfileRepositoryImpl _profileRepository;

  late final FeedService feedService;
  late final OnboardingService onboardingService;
  late final ProfileService profileService;

  void dispose() {
    _httpClient.close();
  }
}
