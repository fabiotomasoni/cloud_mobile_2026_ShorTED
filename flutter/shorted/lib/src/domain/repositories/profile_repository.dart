import '../models/user_profile.dart';

abstract class ProfileRepository {
  Future<UserProfile?> loadProfile();

  Future<void> saveProfile(UserProfile profile);
}
