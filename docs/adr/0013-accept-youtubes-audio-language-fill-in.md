# Accept YouTube filling in a blank audio language

The first real write (Run 1, on one video) showed that YouTube's `videos.update` sets `defaultAudioLanguage` to `en-US` when a Video had none. The app didn't send the field; YouTube fills it in server-side. 278 of the owner's 313 Videos have no audio language, so any bulk edit changes this field on most of them.

We considered three options:
- Letting the owner pick the language to send instead.
- Skipping such Videos, which would leave out most of the channel.
- Accepting YouTube's behaviour.

The owner chose to accept it. The app doesn't try to prevent it. Instead it makes it visible:
- The Apply dialog says how many of the Videos being written have no audio language.
- The Run log notes each one.

This is the one known exception to "only the description changes" (ADR-0002), and it comes from YouTube, not from what the app sends.
