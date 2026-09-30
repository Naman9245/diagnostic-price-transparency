import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import 'booking_draft.dart';
import 'location.dart';
import 'models.dart';
import 'session.dart';

/// Talks to the FastAPI backend in prototype/backend.
///
/// An Android emulator reaches your computer at 10.0.2.2, while web, the iOS
/// simulator and desktop use localhost. On a real phone, pass your computer's
/// Wi-Fi address instead:
///
///     flutter run --dart-define=API_URL=http://192.168.1.20:8000
abstract final class Api {
  static const _override = String.fromEnvironment('API_URL');

  static String get baseUrl {
    if (_override.isNotEmpty) return _override;
    final androidEmulator = !kIsWeb && defaultTargetPlatform == TargetPlatform.android;
    return androidEmulator ? 'http://10.0.2.2:8000' : 'http://localhost:8000';
  }

  /// Every test, with its price range.
  static Future<List<TestItem>> tests() => _getList('/tests', TestItem.fromJson);

  /// Hospitals and their distance from [area]. With [testId], only those
  /// offering that test, cheapest first.
  static Future<List<Hospital>> hospitals({required Area area, String? testId}) {
    // `?testId` leaves the entry out entirely when testId is null.
    return _getList('/hospitals', Hospital.fromJson, {..._near(area), 'test_id': ?testId});
  }

  static Future<List<Specialty>> specialties() => _getList('/specialties', Specialty.fromJson);

  /// Doctors at partner hospitals, nearest to [area] first. With
  /// [hospitalId], only that hospital's.
  static Future<List<Doctor>> doctors({required Area area, String? hospitalId}) =>
      _getList('/doctors', Doctor.fromJson, {..._near(area), 'hospital_id': ?hospitalId});

  static Future<Doctor> doctor(String id, {required Area area}) async =>
      Doctor.fromJson(await _send('GET', '/doctors/$id', query: _near(area)));

  // Signing in. The demo texts nobody: the code comes back in the reply.

  /// Asks for a sign-in code for [phone], and returns it for the app to show.
  static Future<String> sendCode(String phone) async =>
      (await _send('POST', '/auth/code', body: {'phone': phone}))['demo_code'];

  /// Swaps the code for a sign-in token. The first sign-in creates the
  /// account, which has no name yet.
  static Future<(String, User)> verifyCode(String phone, String code) async {
    final body = await _send('POST', '/auth/verify', body: {'phone': phone, 'code': code});
    return (body['token'] as String, User.fromJson(body['user']));
  }

  static Future<User> me() async => User.fromJson(await _send('GET', '/me'));

  static Future<User> updateName(String name) async =>
      User.fromJson(await _send('PUT', '/me', body: {'name': name}));

  static Future<void> signOut() => _send('POST', '/auth/sign-out');

  // Bookings belong to whoever is signed in.

  /// Your bookings, soonest first.
  static Future<List<Booking>> bookings() => _getList('/bookings', Booking.fromJson);

  /// Books a test at a partner lab, for the day, time and place in [draft].
  static Future<Booking> bookTest(Hospital lab, TestItem test, BookingDraft draft) =>
      _book(draft, {'hospital_id': lab.id, 'test_id': test.id, 'home_collection': draft.atHome});

  /// Books an appointment with [doctor], for the day and time in [draft].
  static Future<Booking> bookDoctor(Doctor doctor, BookingDraft draft) =>
      _book(draft, {'doctor_id': doctor.id});

  static Future<Booking> _book(BookingDraft draft, Map<String, Object> item) async {
    final date = draft.day.toIso8601String().substring(0, 10);
    final body = {...item, 'date': date, 'time': draft.time!};
    return Booking.fromJson(await _send('POST', '/bookings', body: body));
  }

  static Future<List<T>> _getList<T>(
    String path,
    T Function(Map<String, dynamic> json) fromJson, [
    Map<String, String>? query,
  ]) async {
    final List<dynamic> body = await _send('GET', path, query: query);
    return [for (final json in body) fromJson(json)];
  }

  static Map<String, String> _near(Area area) => {'lat': '${area.lat}', 'lng': '${area.lng}'};

  /// Sends a request and decodes the JSON reply. Every failure becomes an
  /// [ApiException] whose message a screen can show as it is.
  ///
  /// Once you're signed in, every request carries your token. If the server
  /// turns it down (it forgets sign-ins when it restarts), you're signed out
  /// here too.
  static Future<dynamic> _send(
    String method,
    String path, {
    Map<String, String>? query,
    Object? body,
  }) async {
    final token = Session.token;
    final request = http.Request(
      method,
      Uri.parse('$baseUrl$path').replace(queryParameters: query),
    );
    if (token != null) request.headers['Authorization'] = 'Bearer $token';
    if (body != null) {
      request.headers['Content-Type'] = 'application/json';
      request.body = jsonEncode(body);
    }

    final http.Response response;
    try {
      response = await request
          .send()
          .then(http.Response.fromStream)
          .timeout(const Duration(seconds: 8));
    } catch (_) {
      throw ApiException(
        "Can't reach the RateCard server at $baseUrl. Start the backend, then try again.",
      );
    }
    if (response.statusCode == 401 && token != null) {
      await Session.clear();
      throw ApiException('Your sign-in has expired. Please sign in again.');
    }

    final Object? json;
    try {
      // Decode as UTF-8 by hand: FastAPI doesn't name a charset, and the http
      // package would otherwise garble ₹ and –. A 204 has no body at all.
      json = response.bodyBytes.isEmpty ? null : jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw ApiException("The server sent something that isn't JSON (${response.statusCode}).");
    }
    if (response.statusCode >= 400) {
      throw ApiException(switch (json) {
        {'detail': final String detail} => detail,
        // FastAPI lists validation errors; the first says what's wrong.
        {'detail': [{'msg': final String first}, ...]} => first,
        _ => 'The server returned an error (${response.statusCode}).',
      });
    }
    return json;
  }
}

/// Starts two requests together and waits for both, which is quicker than
/// one after the other. If either fails, its own error is rethrown, so the
/// screen shows the usual message.
Future<(A, B)> both<A, B>(Future<A> first, Future<B> second) async {
  try {
    return await (first, second).wait;
  } on ParallelWaitError<Object?, (AsyncError?, AsyncError?)> catch (e) {
    final failure = (e.errors.$1 ?? e.errors.$2)!;
    Error.throwWithStackTrace(failure.error, failure.stackTrace);
  }
}

class ApiException implements Exception {
  ApiException(this.message);

  final String message;

  @override
  String toString() => message;
}
