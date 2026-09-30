import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

/// Gives anything tappable a press animation: it shrinks a little while a
/// finger or mouse button is down, then springs back.
///
/// It only listens to raw pointer events, so the child keeps its own tap
/// handling, ripple, semantics and keyboard support. The press lets go as
/// soon as the pointer moves like a scroll, so scrolling a list never leaves
/// a row squashed. With reduce motion on, it does nothing.
class Pressable extends StatefulWidget {
  const Pressable({super.key, required this.child, this.scale = 0.95, this.enabled = true});

  final Widget child;

  /// How small the child gets while pressed: 0.95 for buttons and chips,
  /// closer to 1 for wide rows.
  final double scale;

  /// Off for disabled buttons, which shouldn't react.
  final bool enabled;

  @override
  State<Pressable> createState() => _PressableState();
}

class _PressableState extends State<Pressable> {
  // A quick tap still shows the press for at least this long.
  static const _minimumPress = Duration(milliseconds: 90);

  bool _pressed = false;

  /// Where the current press started, or null once it has been let go.
  Offset? _start;
  DateTime _pressedAt = DateTime.now();

  /// Counts presses, so a late release can't cancel a newer press.
  int _presses = 0;

  void _down(PointerDownEvent event) {
    _start = event.position;
    _pressedAt = DateTime.now();
    _presses++;
    setState(() => _pressed = true);
  }

  void _move(PointerMoveEvent event) {
    final start = _start;
    if (start != null && (event.position - start).distance > kTouchSlop) _up();
  }

  Future<void> _up([PointerEvent? _]) async {
    if (_start == null) return; // already let go, e.g. by a scroll
    _start = null;
    final press = _presses;
    final held = DateTime.now().difference(_pressedAt);
    if (held < _minimumPress) await Future<void>.delayed(_minimumPress - held);
    if (mounted && press == _presses) setState(() => _pressed = false);
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.enabled || MediaQuery.disableAnimationsOf(context)) return widget.child;
    return Listener(
      onPointerDown: _down,
      onPointerMove: _move,
      onPointerUp: _up,
      onPointerCancel: _up,
      child: AnimatedScale(
        scale: _pressed ? widget.scale : 1,
        duration: const Duration(milliseconds: 120),
        curve: Curves.easeOut,
        child: widget.child,
      ),
    );
  }
}
