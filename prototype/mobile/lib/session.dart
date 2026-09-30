import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';

/// Someone who has signed in with their mobile number.
class User {
  User.fromJson(Map<String, dynamic> json) : phone = json['phone'], name = json['name'];

  /// Ten digits, without the +91.
  final String phone;

  /// Null until they've said what to call them.
  final String? name;

  /// "Ananya" from "Ananya Rao", for greetings.
  String? get firstName => name?.split(' ').first;

  Map<String, dynamic> toJson() => {'phone': phone, 'name': name};
}

/// Who's signed in, or null. Screens that show your name or bookings listen
/// to it.
final currentUser = ValueNotifier<User?>(null);

/// The sign-in token and who it belongs to, saved on the phone so the app
/// opens signed in without asking the server.
abstract final class Session {
  static const _key = 'session';
  static String? _token;

  /// What [Api] sends with every request, or null when signed out.
  static String? get token => _token;

  /// Picks up the sign-in saved last time. `main` awaits it before the first
  /// frame, because it decides which page opens.
  static Future<void> restore() async {
    final saved = (await SharedPreferences.getInstance()).getString(_key);
    if (saved == null) return;
    final json = jsonDecode(saved);
    _token = json['token'];
    currentUser.value = User.fromJson(json['user']);
    // The server forgets sign-ins when it restarts, so check in the
    // background: [Api] signs out here if the token is turned down. A reply
    // that arrives after signing out, or in again, is ignored.
    final token = _token;
    Api.me().then((user) async {
      if (_token == token) await updateUser(user);
    }).ignore();
  }

  static Future<void> signIn(String token, User user) {
    _token = token;
    return updateUser(user);
  }

  /// Shows [user]'s details everywhere and saves them with the token.
  static Future<void> updateUser(User user) async {
    currentUser.value = user;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, jsonEncode({'token': _token, 'user': user.toJson()}));
  }

  /// Tells the server to forget the token if it can be reached, and forgets
  /// the sign-in here either way.
  static Future<void> signOut() async {
    try {
      await Api.signOut();
    } on ApiException {
      // Offline, or the token had already expired: nobody can use it now.
    }
    await clear();
  }

  /// Forgets the sign-in on this phone only. [Api] calls it when the server
  /// turns the token down.
  static Future<void> clear() async {
    _token = null;
    currentUser.value = null;
    await (await SharedPreferences.getInstance()).remove(_key);
  }
}

/// True when you're signed in, opening the sign-in page first if you
/// aren't. Signing in counts once the code is right, even if you leave
/// before giving a name. Anything that needs an account, like booking, asks
/// this first; browsing never does.
Future<bool> ensureSignedIn(BuildContext context) async {
  if (currentUser.value == null) await Navigator.pushNamed(context, '/login');
  return currentUser.value != null;
}
