# Voice Assistant (J.A.R.V.I.S) Architecture Rules

When modifying or maintaining the voice assistant features (`live.rs`, `caf.py`, `chat.ts`), you MUST adhere to the following architectural constraints to prevent infinite loops, audio glitching, and connection drops:

1. **Continuous Audio Streaming (Echo Suppression)**
   - When suppressing speaker echo from the microphone, **DO NOT DROP PACKETS**. Completely dropping packets will starve the Gemini WebSocket connection and cause it to timeout ("dejó de responder").
   - Instead, **SEND SILENCE** (a buffer of zeros) to the WebSocket. This keeps the stream alive without triggering the model's VAD.

2. **VAD (Voice Activity Detection)**
   - **DO NOT** rely solely on RMS (volume) thresholds to trigger `TURN_COMPLETE`. Continuous background noise (AC/fans) will defeat it and cause infinite listening loops.
   - You MUST use an acoustic model (e.g., Vosk) to detect the actual endpoints of human speech. If Vosk detects no words for 2 seconds (only noise), you must drop the turn and return to silence without sending `TURN_COMPLETE`.

3. **Audio Playback Buffering**
   - The Gemini Live API may send `inlineData` in tiny chunks (as small as 2 bytes). 
   - **DO NOT** queue these chunks directly into `rodio` or any audio sink one-by-one. You must aggregate or concatenate chunks before appending them to the audio sink to prevent severe playback glitching and thread blocking.

4. **Microphone Exclusivity (UI vs Background)**
   - The UI Dictation Microphone (click-to-talk in the chat box) and the Background Wake-Word Engine (e.g., `caf.py`) must remain completely separate.
   - **DO NOT** create auto-reply loops where the UI dictation mic turns itself back on automatically after an assistant response. The background engine (`is_live`) is the sole provider of "always-on" voice interaction.
