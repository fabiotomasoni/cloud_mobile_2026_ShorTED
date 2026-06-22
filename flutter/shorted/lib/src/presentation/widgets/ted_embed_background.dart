import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../../domain/models/snack.dart';

class TedEmbedBackground extends StatefulWidget {
  const TedEmbedBackground({super.key, required this.snack});

  final Snack snack;

  @override
  State<TedEmbedBackground> createState() => _TedEmbedBackgroundState();
}

class _TedEmbedBackgroundState extends State<TedEmbedBackground> {
  late final WebViewController _controller;

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(Colors.black)
      ..loadRequest(widget.snack.embedUri);
  }

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: Colors.black,
      child: WebViewWidget(controller: _controller),
    );
  }
}
