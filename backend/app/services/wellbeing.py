"""Versioned, gentle wellbeing prompts and a transparent non-clinical score."""

from __future__ import annotations

from typing import Any


DIMENSIONS: dict[str, str] = {
    "mood": "Mood",
    "connection": "Connection",
    "awareness": "Emotional awareness",
    "empathy": "Empathy",
    "coping": "Coping",
    "confidence": "Confidence",
    "engagement": "Enjoyment",
}


_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "mood_today",
        "prompt": "Which face feels a little like you today?",
        "scene": "Choose the feeling that is closest, or simply feels right.",
        "visual": "faces",
        "choices": [
            {"id": "bright", "label": "Happy", "emoji": "😊", "scores": {"mood": 5, "awareness": 5}},
            {"id": "okay", "label": "Okay", "emoji": "🙂", "scores": {"mood": 4, "awareness": 4}},
            {"id": "quiet", "label": "Neutral", "emoji": "😐", "scores": {"mood": 3, "awareness": 4}},
            {"id": "uneasy", "label": "Worried", "emoji": "😟", "scores": {"mood": 2, "awareness": 4}},
            {"id": "low", "label": "Sad", "emoji": "😔", "scores": {"mood": 1, "awareness": 4}},
        ],
    },
    {
        "id": "good_news",
        "prompt": "You hear some good news. What might you feel?",
        "scene": "A friendly character has a little happy surprise.",
        "visual": "celebration",
        "choices": [
            {"id": "excited", "label": "Excited", "emoji": "🤩", "scores": {"mood": 5, "engagement": 5}},
            {"id": "pleased", "label": "Pleased", "emoji": "😊", "scores": {"mood": 5, "engagement": 4}},
            {"id": "calm", "label": "Calm", "emoji": "😌", "scores": {"mood": 4, "engagement": 4}},
            {"id": "unsure", "label": "Not sure", "emoji": "🤔", "scores": {"mood": 3, "engagement": 3}},
        ],
    },
    {
        "id": "friendly_call",
        "prompt": "A familiar person calls to say hello. What sounds nice?",
        "scene": "Two friendly characters wave from their homes.",
        "visual": "connection",
        "choices": [
            {"id": "long_chat", "label": "A chat together", "emoji": "💬", "scores": {"connection": 5}},
            {"id": "short_hello", "label": "A short hello", "emoji": "👋", "scores": {"connection": 4}},
            {"id": "later", "label": "Maybe later", "emoji": "🕰️", "scores": {"connection": 3}},
            {"id": "quiet_time", "label": "Quiet time", "emoji": "🌿", "scores": {"connection": 4}},
        ],
    },
    {
        "id": "helping_hand",
        "prompt": "Someone nearby drops a bag. What might you do?",
        "scene": "A few groceries have rolled beside a friendly character.",
        "visual": "helping",
        "choices": [
            {"id": "offer_help", "label": "Offer to help", "emoji": "❤️", "scores": {"empathy": 5}},
            {"id": "ask_first", "label": "Ask if they’re okay", "emoji": "🙂", "scores": {"empathy": 5}},
            {"id": "find_someone", "label": "Find someone nearby", "emoji": "🤝", "scores": {"empathy": 4}},
            {"id": "not_sure_help", "label": "I’m not sure", "emoji": "🤔", "scores": {"empathy": 3}},
        ],
    },
    {
        "id": "small_disagreement",
        "prompt": "Two people disagree. What feels like a good next step?",
        "scene": "Two cartoon friends are talking, with a calm helper nearby.",
        "visual": "conversation",
        "choices": [
            {"id": "listen", "label": "Listen calmly", "emoji": "👂", "scores": {"empathy": 5, "coping": 5}},
            {"id": "gentle_words", "label": "Talk gently", "emoji": "💬", "scores": {"empathy": 5, "coping": 5}},
            {"id": "pause", "label": "Take a short pause", "emoji": "🌱", "scores": {"empathy": 4, "coping": 5}},
            {"id": "ask_support", "label": "Ask someone to help", "emoji": "🤝", "scores": {"empathy": 4, "coping": 4}},
        ],
    },
    {
        "id": "change_of_plan",
        "prompt": "A plan changes at the last minute. What could help?",
        "scene": "A friendly character sees a new path appear on a map.",
        "visual": "new_path",
        "choices": [
            {"id": "slow_breath", "label": "Take a slow breath", "emoji": "🌬️", "scores": {"coping": 5, "awareness": 5}},
            {"id": "ask_next", "label": "Ask what happens next", "emoji": "❔", "scores": {"coping": 5, "awareness": 4}},
            {"id": "take_time", "label": "Take a little time", "emoji": "🌿", "scores": {"coping": 4, "awareness": 4}},
            {"id": "not_sure_change", "label": "I’m not sure yet", "emoji": "🤔", "scores": {"coping": 3, "awareness": 3}},
        ],
    },
    {
        "id": "small_success",
        "prompt": "You finish a small task. How might that feel?",
        "scene": "A character puts a book back and gives themself a little cheer.",
        "visual": "small_win",
        "choices": [
            {"id": "proud", "label": "Proud", "emoji": "✨", "scores": {"confidence": 5, "engagement": 5}},
            {"id": "glad_done", "label": "Glad it’s done", "emoji": "😊", "scores": {"confidence": 4, "engagement": 4}},
            {"id": "ready_rest", "label": "Ready for a rest", "emoji": "🛋️", "scores": {"confidence": 4, "engagement": 4}},
            {"id": "no_feeling", "label": "Not sure", "emoji": "😐", "scores": {"confidence": 3, "engagement": 3}},
        ],
    },
    {
        "id": "enjoyable_moment",
        "prompt": "Which little moment sounds good today?",
        "scene": "Pick a cozy activity from a few friendly picture cards.",
        "visual": "activity",
        "choices": [
            {"id": "music", "label": "Listen to music", "emoji": "🎵", "scores": {"engagement": 5, "mood": 4}},
            {"id": "someone", "label": "Talk with someone", "emoji": "💬", "scores": {"engagement": 4, "connection": 5}},
            {"id": "outside", "label": "Sit outside", "emoji": "🌤️", "scores": {"engagement": 4, "mood": 4}},
            {"id": "rest", "label": "Rest quietly", "emoji": "🌙", "scores": {"engagement": 4, "mood": 4}},
        ],
    },
]


def public_questions() -> list[dict[str, Any]]:
    """Return prompts and answer choices without internal scoring values."""
    return [
        {
            "id": question["id"],
            "prompt": question["prompt"],
            "scene": question["scene"],
            "visual": question["visual"],
            "choices": [
                {"id": choice["id"], "label": choice["label"], "emoji": choice["emoji"]}
                for choice in question["choices"]
            ],
        }
        for question in _QUESTIONS
    ]


def score_answers(answers: dict[str, str]) -> dict[str, Any]:
    """Validate a full answer set, calculate category scores, and create snapshots."""
    questions_by_id = {question["id"]: question for question in _QUESTIONS}
    if set(answers) != set(questions_by_id):
        raise ValueError("Please answer each of the daily check-in questions.")

    dimension_values: dict[str, list[int]] = {key: [] for key in DIMENSIONS}
    snapshots: list[dict[str, str]] = []
    for question in _QUESTIONS:
        answer_id = answers[question["id"]]
        option = next((item for item in question["choices"] if item["id"] == answer_id), None)
        if option is None:
            raise ValueError("One of the selected answers is not available.")
        for dimension, value in option["scores"].items():
            dimension_values[dimension].append(value)
        snapshots.append({
            "question_id": question["id"],
            "prompt": question["prompt"],
            "scene": question["scene"],
            "answer_id": option["id"],
            "answer": option["label"],
            "emoji": option["emoji"],
        })

    # Each dimension is the mean of its related 1–5 choice ratings, normalized to 0–100.
    category_scores = {
        dimension: round((sum(values) / len(values) - 1) * 25)
        for dimension, values in dimension_values.items()
        if values
    }
    overall_score = round(sum(category_scores.values()) / len(category_scores))
    lowest_dimension = min(category_scores, key=category_scores.get)
    highest_dimension = max(category_scores, key=category_scores.get)
    supportive_ideas = {
        "mood": "a comforting moment",
        "connection": "a chance to connect",
        "awareness": "a quiet moment to notice feelings",
        "empathy": "a kind conversation",
        "coping": "some time to pause",
        "confidence": "a small, familiar activity",
        "engagement": "an enjoyable activity",
    }
    positive_highlights = {
        "mood": "a brighter mood",
        "connection": "moments of connection",
        "awareness": "noticing feelings",
        "empathy": "thoughtfulness",
        "coping": "ways to manage changes",
        "confidence": "confidence in small steps",
        "engagement": "enjoyment",
    }
    if overall_score < 60 or min(category_scores.values()) < 45:
        category = "Could Use Some Support Today"
        summary = (
            f"Today's answers suggest {supportive_ideas[lowest_dimension]} may feel welcome. "
            "A gentle check-in or a comforting activity could be nice today."
        )
    elif overall_score >= 70 and min(category_scores.values()) >= 45:
        category = "Doing Well Today"
        summary = (
            f"Today's answers suggest a generally positive day, with "
            f"{positive_highlights[highest_dimension]} coming through strongly."
        )
    else:
        category = "Feeling Okay Today"
        idea = supportive_ideas[lowest_dimension]
        summary = f"Today's answers suggest a mix of experiences. {idea.capitalize()} may feel welcome."

    return {
        "answers": snapshots,
        "overall_score": overall_score,
        "overall_category": category,
        "category_scores": category_scores,
        "summary": summary,
    }
