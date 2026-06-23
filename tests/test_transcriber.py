from transcriber import build_transcript_text, format_timestamp


def test_timestamp_format() -> None:
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(65) == "01:05"


def test_speaker_labeled_transcript() -> None:
    text = build_transcript_text(
        [
            {"speaker": "PATIENT", "text": "Hello", "timestamp": 0},
            {
                "speaker": "AGENT",
                "text": "How can I help?",
                "timestamp": 4.2,
                "confidence": 0.91,
            },
        ]
    )
    assert "[00:00] PATIENT: Hello" in text
    assert "[00:04] AGENT: How can I help?" in text
    assert "ASR confidence: 0.91" in text
