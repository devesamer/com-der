echo "starting VideoCompressor ~@VIDEO_COMPRESS_BOT";
gunicorn app:app & python3 -m main
