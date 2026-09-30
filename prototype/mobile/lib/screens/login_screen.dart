import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api.dart';
import '../format.dart';
import '../session.dart';
import '../theme.dart';
import '../widgets/common.dart';
import '../widgets/pressable.dart';

enum _Step { phone, code, name }

/// Signing in: a mobile number, the code sent to it and, the first time, a
/// name. It's the first page until you've signed in, with a way to skip it
/// (browsing needs no account), and it opens on top of other pages when
/// something needs an account, such as booking.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  /// An Indian mobile number: ten digits, starting 6, 7, 8 or 9.
  static final _mobile = RegExp(r'^[6-9]\d{9}$');

  final _phone = TextEditingController();
  final _code = TextEditingController();
  final _name = TextEditingController();
  var _step = _Step.phone;
  String? _demoCode, _error;
  bool _busy = false;

  @override
  void dispose() {
    _phone.dispose();
    _code.dispose();
    _name.dispose();
    super.dispose();
  }

  /// Whether another page opened this one, rather than the app starting on it.
  bool get _pushed => ModalRoute.canPopOf(context) ?? false;

  bool get _ready => switch (_step) {
    _Step.phone => _mobile.hasMatch(_phone.text),
    _Step.code => _code.text.length == 6,
    _Step.name => _name.text.trim().isNotEmpty,
  };

  /// Sends the current step, with a spinner on the button meanwhile. Then
  /// shows the next step, or the server's message under the field.
  Future<void> _submit() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final next = await switch (_step) {
        _Step.phone => _sendCode(),
        _Step.code => _verify(),
        _Step.name => _saveName(),
      };
      if (!mounted) return;
      if (next == null) {
        _finish();
      } else {
        setState(() => _step = next);
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  // Each step returns the one to show next, or null once you're signed in.

  Future<_Step?> _sendCode() async {
    _demoCode = await Api.sendCode(_phone.text);
    _code.clear();
    return _Step.code;
  }

  /// A first sign-in creates the account, which then needs a name.
  Future<_Step?> _verify() async {
    final (token, user) = await Api.verifyCode(_phone.text, _code.text);
    await Session.signIn(token, user);
    return user.name == null ? _Step.name : null;
  }

  Future<_Step?> _saveName() async {
    await Session.updateUser(await Api.updateName(_name.text.trim()));
    return null;
  }

  /// Back to the page that asked for a sign-in, or on to the tabs.
  void _finish() {
    if (_pushed) {
      Navigator.pop(context);
    } else {
      _openTabs();
    }
  }

  void _openTabs() => Navigator.pushReplacementNamed(context, '/');

  @override
  Widget build(BuildContext context) {
    final (label, action) = switch (_step) {
      _Step.phone => ('Your mobile number', 'Send code'),
      _Step.code => ('Enter the code sent to ${phoneNumber(_phone.text)}', 'Verify'),
      _Step.name => ('What should we call you?', 'Continue'),
    };
    return Scaffold(
      appBar: _pushed
          ? pageBar()
          : AppBar(
              automaticallyImplyLeading: false,
              actions: [
                Pressable(
                  child: TextButton(onPressed: _openTabs, child: const Text('Skip for now')),
                ),
                const SizedBox(width: 8),
              ],
            ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(24, 8, 24, 32),
        children: [
          const Center(
            child: CircleAvatar(
              radius: 36,
              backgroundColor: AppColors.mint,
              child: Icon(Icons.currency_rupee_rounded, size: 36, color: AppColors.teal),
            ),
          ),
          const SizedBox(height: 16),
          const Text('Welcome to RateCard', textAlign: TextAlign.center, style: AppText.heading),
          const SizedBox(height: 6),
          const Text(
            'Sign in to book tests and doctors, and keep your bookings in one place.',
            textAlign: TextAlign.center,
            style: AppText.body,
          ),
          const SizedBox(height: 32),
          Text(label, style: AppText.section),
          const SizedBox(height: 10),
          _field(),
          if (_step == _Step.code) ...[
            const SizedBox(height: 12),
            DemoNotice(text: 'No text is sent. Your code is $_demoCode'),
          ],
          const SizedBox(height: 20),
          PrimaryButton(label: action, busy: _busy, onPressed: _ready ? _submit : null),
          if (_step == _Step.code)
            Pressable(
              child: TextButton(
                onPressed: _busy
                    ? null
                    : () => setState(() {
                        _step = _Step.phone;
                        _error = null;
                      }),
                child: const Text('Change number'),
              ),
            ),
        ],
      ),
    );
  }

  /// The current step's field. Each step gets a new one, which takes the
  /// focus as it appears.
  Widget _field() => switch (_step) {
    _Step.phone => _input(
      _phone,
      hint: '98765 43210',
      autofill: AutofillHints.telephoneNumberNational,
      digits: 10,
      prefix: const Padding(
        padding: EdgeInsets.only(left: 14, right: 10),
        child: Text('+91', style: _fieldText),
      ),
    ),
    _Step.code => _input(
      _code,
      hint: '6-digit code',
      autofill: AutofillHints.oneTimeCode,
      digits: 6,
    ),
    _Step.name => _input(_name, hint: 'Your name', autofill: AutofillHints.name),
  };

  static const _fieldText = TextStyle(fontSize: 16, fontWeight: FontWeight.w600);

  /// A field for [digits] digits and nothing else, or for a name when
  /// [digits] is null.
  TextField _input(
    TextEditingController controller, {
    required String hint,
    required String autofill,
    int? digits,
    Widget? prefix,
  }) {
    return TextField(
      key: ObjectKey(controller),
      controller: controller,
      autofocus: true,
      autofillHints: [autofill],
      keyboardType: digits == null ? TextInputType.name : TextInputType.number,
      textCapitalization: digits == null ? TextCapitalization.words : TextCapitalization.none,
      inputFormatters: [
        if (digits != null) ...[
          FilteringTextInputFormatter.digitsOnly,
          LengthLimitingTextInputFormatter(digits),
        ],
      ],
      onChanged: (_) => setState(() => _error = null),
      onSubmitted: (_) {
        if (_ready && !_busy) _submit();
      },
      style: _fieldText,
      decoration: InputDecoration(
        hintText: hint,
        errorText: _error,
        prefixIcon: prefix,
        // At its own size the +91 is centred, level with the digits.
        prefixIconConstraints: const BoxConstraints(),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 16),
      ),
    );
  }
}
