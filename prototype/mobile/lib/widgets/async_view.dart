import 'package:flutter/material.dart';

import 'common.dart';

/// Shows what a [future] loaded, a pulsing placeholder until it arrives, and
/// the error with a retry button if it fails. Every screen that loads data
/// uses it, so they all behave the same way.
class AsyncView<T> extends StatelessWidget {
  const AsyncView({
    super.key,
    required this.future,
    required this.onRetry,
    required this.builder,
    this.placeholder = const LoadingRows(),
    this.frame,
  });

  final Future<T> future;
  final VoidCallback onRetry;
  final Widget Function(BuildContext context, T data) builder;
  final Widget placeholder;

  /// Wraps the loading and error states. Pages whose [builder] returns a
  /// whole Scaffold pass one here, so the back button is there throughout.
  final Widget Function(Widget child)? frame;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<T>(
      future: future,
      builder: (context, snapshot) {
        final Widget child;
        if (snapshot.hasError && snapshot.connectionState != ConnectionState.waiting) {
          child = ErrorView(message: '${snapshot.error}', onRetry: onRetry);
        } else if (snapshot.hasData) {
          // While refreshing, the last data stays on screen.
          return builder(context, snapshot.data as T);
        } else {
          child = placeholder;
        }
        return frame?.call(child) ?? child;
      },
    );
  }
}

/// For screens that load one thing: holds the [future], and can [reload] it
/// (retry) or [refresh] it (pull to refresh).
mixin Reloadable<W extends StatefulWidget, T> on State<W> {
  /// Loads the screen's data. Called once at first, then on each reload.
  Future<T> fetch();

  /// Reloads the screen whenever this changes, such as `currentArea` for
  /// anything measured from where you are. Nothing by default.
  Listenable? get reloadOn => null;

  late Future<T> future = _start();

  @override
  void initState() {
    super.initState();
    reloadOn?.addListener(reload);
  }

  @override
  void dispose() {
    reloadOn?.removeListener(reload);
    super.dispose();
  }

  void reload() => setState(() => future = _start());

  // `ignore` stops a failed request counting as an uncaught error while no
  // AsyncView is listening yet, for example on a tab that hasn't been laid
  // out. AsyncView still gets the error and shows it once it's on screen.
  Future<T> _start() => fetch()..ignore();

  Future<void> refresh() async {
    reload();
    try {
      await future;
    } catch (_) {
      // AsyncView shows the error; the refresh spinner just needs to stop.
    }
  }
}
