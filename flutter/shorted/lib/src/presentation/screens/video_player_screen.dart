import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:chewie/chewie.dart';
import 'package:video_player/video_player.dart';

import '../../domain/models/snack.dart';

Future<void> showSnackVideoPlayer(BuildContext context, Snack snack) {
  final mediaUrl = snack.mediaUri;
  if (mediaUrl == null) {
    return showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Video non disponibile'),
        content: const Text('Questo snack non ha ancora un URL video riproducibile.'),
        actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('OK'))],
      ),
    );
  }

  return showGeneralDialog<void>(
    context: context,
    barrierColor: Colors.black,
    barrierDismissible: false,
    barrierLabel: 'Video player',
    pageBuilder: (_, _, _) => SnackVideoOverlay(mediaUrl: mediaUrl, startTime: snack.startTime),
  );
}

class SnackVideoOverlay extends StatefulWidget {
  const SnackVideoOverlay({super.key, required this.mediaUrl, required this.startTime});

  final Uri mediaUrl;
  final int startTime;

  @override
  State<SnackVideoOverlay> createState() => _SnackVideoOverlayState();
}

class _SnackVideoOverlayState extends State<SnackVideoOverlay> {
  late final VideoPlayerController _videoController;
  ChewieController? _chewieController;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _allowVideoOrientations();
    _videoController = VideoPlayerController.networkUrl(widget.mediaUrl);
    _initializePlayer();
  }

  @override
  void dispose() {
    _restorePortraitOrientation();
    _chewieController?.dispose();
    _videoController.dispose();
    super.dispose();
  }

  Future<void> _allowVideoOrientations() {
    return SystemChrome.setPreferredOrientations(DeviceOrientation.values);
  }

  Future<void> _restorePortraitOrientation() {
    return SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
      DeviceOrientation.portraitDown,
    ]);
  }

  Future<void> _initializePlayer() async {
    try {
      await _videoController.initialize();
      if (widget.startTime > 0) {
        await _videoController.seekTo(Duration(seconds: widget.startTime));
      }
      if (!mounted) {
        return;
      }
      setState(() {
        _chewieController = ChewieController(
          videoPlayerController: _videoController,
          autoPlay: true,
          allowFullScreen: false,
          allowMuting: true,
          showControls: true,
          materialProgressColors: ChewieProgressColors(
            playedColor: Theme.of(context).colorScheme.primary,
            handleColor: Theme.of(context).colorScheme.primary,
          ),
        );
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error);
    }
  }

  @override
  Widget build(BuildContext context) {
    final chewieController = _chewieController;
    return Material(
      color: Colors.black,
      child: Stack(
        fit: StackFit.expand,
        children: [
          if (_error != null)
            Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.error_outline, color: Colors.white70, size: 42),
                    const SizedBox(height: 12),
                    Text('Video non riproducibile', style: Theme.of(context).textTheme.titleMedium?.copyWith(color: Colors.white)),
                    const SizedBox(height: 8),
                    const Text('Il player nativo non riesce ad aprire questo URL media.', textAlign: TextAlign.center, style: TextStyle(color: Colors.white70)),
                  ],
                ),
              ),
            )
          else if (chewieController == null)
            const Center(child: CircularProgressIndicator())
          else
            SafeArea(child: Chewie(controller: chewieController)),
          SafeArea(
            child: Align(
              alignment: Alignment.topLeft,
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: IconButton.filledTonal(
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.close),
                  tooltip: 'Close player',
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
