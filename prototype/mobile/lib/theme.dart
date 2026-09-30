import 'package:flutter/material.dart';

/// Colours shared by every screen.
///
/// The look follows a mint-and-teal doctor-booking design (credited in the
/// README): white screens, one calm teal for actions, soft mint tints behind
/// chips and icons, and yellow stars for ratings.
//
// The reference design's teal (#3C887E) is deepened a little here, so white
// text on it passes the WCAG AA contrast ratio of 4.5:1. Text sitting on the
// mint tint uses tealDark for the same reason.
abstract final class AppColors {
  static const teal = Color(0xFF347A71); // actions, the banner, selected states
  static const tealDark = Color(0xFF2A665E); // text on mint, the banner's gradient
  static const mint = Color(0xFFE3EFED); // behind chips, tabs and icons
  static const cloud = Color(0xFFF0F3F5); // unselected day and time chips, inputs
  static const ink = Color(0xFF1D2327); // main text
  static const slate = Color(0xFF6B747B); // secondary text
  static const line = Color(0xFFE5EAEC); // borders and dividers
  static const star = Color(0xFFF5B82E); // rating stars
  static const amber = Color(0xFFE3A21A); // the middle of the price strip
  static const coral = Color(0xFFC4453C); // the priciest price, low ratings, emergency
  static const demo = Color(0xFFF8CB46); // the yellow DEMO badge
  static const caution = Color(0xFFFFF4E0); // behind preparation notes
  static const cautionInk = Color(0xFF7A4B00);
}

/// The bundled typeface, Plus Jakarta Sans. It has a proper ₹ sign.
const kFontFamily = 'PlusJakartaSans';

/// Text styles used on more than one screen.
abstract final class AppText {
  static const heading = TextStyle(
    fontSize: 19,
    fontWeight: FontWeight.w700,
    color: AppColors.ink,
    height: 1.25,
  );
  static const section = TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.ink);
  static const title = TextStyle(
    fontSize: 15,
    fontWeight: FontWeight.w700,
    color: AppColors.ink,
    height: 1.25,
  );
  static const body = TextStyle(fontSize: 13.5, color: AppColors.slate, height: 1.55);
  static const muted = TextStyle(fontSize: 12.5, color: AppColors.slate, height: 1.35);
  static const price = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w800,
    color: AppColors.ink,
    fontFeatures: [FontFeature.tabularFigures()],
  );
}

/// Icon and colour for a test category ("Blood") or a doctor's specialty id
/// ("cardiology"): the round tiles and the icons beside names. A test and a
/// specialty for the same part of the body share a look.
(IconData, Color) categoryStyle(String category) => switch (category.toLowerCase()) {
  'blood' => (Icons.bloodtype_outlined, const Color(0xFFE0584F)),
  'heart' || 'cardiology' => (Icons.monitor_heart_outlined, const Color(0xFFD9468F)),
  'thyroid' => (Icons.bolt_rounded, const Color(0xFF7C5CD6)),
  'diabetes' => (Icons.water_drop_outlined, const Color(0xFF1FA2A6)),
  'vitamins' => (Icons.wb_sunny_outlined, const Color(0xFFE3A21A)),
  'liver' => (Icons.science_outlined, const Color(0xFF8A5A44)),
  'kidney' => (Icons.filter_alt_outlined, const Color(0xFF3F8ED8)),
  'imaging' => (Icons.accessibility_new_rounded, const Color(0xFF4F5B66)),
  'general' => (Icons.medical_services_outlined, const Color(0xFF3E9B5F)),
  'orthopaedics' => (Icons.directions_walk_rounded, const Color(0xFFE07B39)),
  'dermatology' => (Icons.face_outlined, const Color(0xFFC0674F)),
  'paediatrics' => (Icons.child_care_outlined, const Color(0xFF2D9CDB)),
  'gynaecology' => (Icons.pregnant_woman_outlined, const Color(0xFFB0508A)),
  'ent' => (Icons.hearing_outlined, const Color(0xFF5C6BC0)),
  'neurology' => (Icons.psychology_outlined, const Color(0xFF8E44AD)),
  _ => (Icons.biotech_outlined, AppColors.slate),
};

ThemeData buildTheme() {
  final scheme = ColorScheme.fromSeed(
    seedColor: AppColors.teal,
    primary: AppColors.teal,
    surface: Colors.white,
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    fontFamily: kFontFamily,
    scaffoldBackgroundColor: Colors.white,
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.white,
      foregroundColor: AppColors.ink,
      surfaceTintColor: Colors.transparent,
      scrolledUnderElevation: 0.5,
      centerTitle: true,
      titleTextStyle: TextStyle(
        fontFamily: kFontFamily,
        fontSize: 17,
        fontWeight: FontWeight.w700,
        color: AppColors.ink,
      ),
    ),
    dividerTheme: const DividerThemeData(color: AppColors.line, thickness: 1, space: 1),
    // Every text field looks like the design's search box: grey, no outline.
    inputDecorationTheme: const InputDecorationThemeData(
      filled: true,
      fillColor: AppColors.cloud,
      hoverColor: Colors.transparent,
      isDense: true,
      contentPadding: EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      hintStyle: TextStyle(fontSize: 14.5, color: AppColors.slate),
      errorStyle: TextStyle(color: AppColors.coral),
      errorMaxLines: 3,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.all(Radius.circular(12)),
        borderSide: BorderSide.none,
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: AppColors.teal,
        foregroundColor: Colors.white,
        disabledBackgroundColor: const Color(0xFFB9D4D0),
        disabledForegroundColor: Colors.white,
        minimumSize: const Size(0, 52),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        textStyle: const TextStyle(
          fontFamily: kFontFamily,
          fontSize: 15.5,
          fontWeight: FontWeight.w700,
        ),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.teal,
        side: const BorderSide(color: AppColors.teal),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        textStyle: const TextStyle(fontFamily: kFontFamily, fontWeight: FontWeight.w700),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: AppColors.teal,
        textStyle: const TextStyle(fontFamily: kFontFamily, fontWeight: FontWeight.w700),
      ),
    ),
    floatingActionButtonTheme: const FloatingActionButtonThemeData(
      backgroundColor: AppColors.teal,
      foregroundColor: Colors.white,
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
    ),
    snackBarTheme: const SnackBarThemeData(behavior: SnackBarBehavior.floating),
  );
}
