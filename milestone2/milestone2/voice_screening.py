"""
voice_screening.py
Voice answers that work for real users on their own device, locally and when
deployed. The BROWSER does the audio work (st.audio_input records, the Web
Speech API reads questions aloud); the server only turns the recorded WAV into
text with SpeechRecognition. No microphone or speaker on the server, so no
PyAudio and no pyttsx3.

Needs:  pip install SpeechRecognition     (speech-to-text uses Google's free web API,
                                           so the server needs internet access)
"""

import hashlib
import io
import json

MAX_TRANSCRIBE_SECONDS = 60      # only the first minute is transcribed; the full audio is always saved


def transcribe_wav_bytes(wav_bytes):
    """Transcript of a WAV recording, or '' if no words were recognised.
    Raises RuntimeError with a readable message for real failures."""
    try:
        import speech_recognition as sr
    except ImportError:
        raise RuntimeError("The SpeechRecognition package is missing. Run: pip install SpeechRecognition")

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
            audio = recognizer.record(source, duration=MAX_TRANSCRIBE_SECONDS)
    except Exception as exc:
        raise RuntimeError(f"Could not read the recording: {exc}")

    try:
        return recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as exc:
        raise RuntimeError(f"Speech recognition service error (check the internet connection): {exc}")


def read_aloud_html(text):
    """A self-contained button that speaks `text` in the user's browser."""
    payload = json.dumps(text).replace("</", "<\\/").replace("<!--", "<\\!--")
    return (
        "<button id='speak' style=\"font:600 14px system-ui,sans-serif;padding:8px 14px;"
        "border:1px solid #CBD3DF;border-radius:10px;background:#fff;color:#0F1B2D;cursor:pointer\">"
        "\U0001F50A Read question aloud</button>"
        "<script>(function(){var t=" + payload + ";"
        "document.getElementById('speak').onclick=function(){"
        "var s=window.speechSynthesis;if(!s){return;}"
        "s.cancel();var u=new SpeechSynthesisUtterance(t);u.rate=0.95;s.speak(u);};})();</script>"
    )


def render_voice_controls(question_id, question_text, answer_key, audio_key):
    """Read-aloud button + browser recorder for one interview question.

    On a NEW recording: stores the WAV bytes in session_state[audio_key] and puts the
    transcript into session_state[answer_key] (the caller renders the text box with
    that key AFTER calling this, so the transcript shows up straight away).
    """
    import streamlit as st
    import streamlit.components.v1 as components

    version_key = f"rec_ver_{question_id}"
    hash_key = f"rec_hash_{question_id}"
    version = st.session_state.get(version_key, 0)      # bumping it gives the recorder a fresh, empty state
    has_saved = bool(st.session_state.get(audio_key))

    left, right = st.columns([4, 1])
    with left:
        components.html(read_aloud_html(question_text), height=48)
    with right:
        if has_saved and st.button("\U0001F5D1\uFE0F Clear", key=f"clear_{question_id}", help="Delete this recording"):
            st.session_state[audio_key] = None
            st.session_state[hash_key] = None
            st.session_state[version_key] = version + 1
            st.rerun()

    recording = st.audio_input(
        "Record your answer", key=f"rec_{question_id}_{version}", label_visibility="collapsed"
    )

    if recording is not None:
        data = recording.getvalue()
        digest = hashlib.md5(data).hexdigest()
        if st.session_state.get(hash_key) != digest:         # only act on a NEW recording, not on every rerun
            st.session_state[hash_key] = digest
            st.session_state[audio_key] = data
            transcript = ""
            with st.spinner("Turning your speech into text..."):
                try:
                    transcript = transcribe_wav_bytes(data)
                except RuntimeError as exc:
                    st.error(str(exc))
            if transcript:
                st.session_state[answer_key] = transcript
            else:
                st.warning(
                    "Your recording is saved, but the words could not be made out. "
                    "Type your answer below, or record again."
                )
    elif st.session_state.get(audio_key):
        st.caption("Your saved recording:")
        st.audio(st.session_state[audio_key], format="audio/wav")