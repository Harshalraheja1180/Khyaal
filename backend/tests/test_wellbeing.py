from app.services.wellbeing import DIMENSIONS, public_questions, score_answers


def complete_answers():
    return {question["id"]: question["choices"][0]["id"] for question in public_questions()}


def test_scoring_is_server_side_and_returns_cautious_non_clinical_result():
    public = public_questions()
    assert len(public) == 8
    assert all("scores" not in choice for question in public for choice in question["choices"])

    result = score_answers(complete_answers())
    assert 0 <= result["overall_score"] <= 100
    assert set(result["category_scores"]) == set(DIMENSIONS)
    assert len(result["answers"]) == len(public)
    assert result["overall_category"] in {
        "Doing Well Today", "Feeling Okay Today", "Could Use Some Support Today",
    }
    assert "suggest" in result["summary"].lower()

    lower_day = score_answers({
        "mood_today": "low",
        "good_news": "unsure",
        "friendly_call": "later",
        "helping_hand": "not_sure_help",
        "small_disagreement": "ask_support",
        "change_of_plan": "not_sure_change",
        "small_success": "no_feeling",
        "enjoyable_moment": "rest",
    })
    assert lower_day["overall_category"] == "Could Use Some Support Today"
    assert "comforting moment" in lower_day["summary"]


def test_score_rejects_incomplete_or_invalid_answer_sets():
    answers = complete_answers()
    answers.pop("mood_today")
    try:
        score_answers(answers)
        assert False, "incomplete answers must fail"
    except ValueError as error:
        assert "each" in str(error).lower()

    answers = complete_answers()
    answers["mood_today"] = "not-a-choice"
    try:
        score_answers(answers)
        assert False, "unknown choices must fail"
    except ValueError as error:
        assert "selected" in str(error).lower()


def test_daily_checkin_submission_history_reports_permissions_and_reset(client, register_user, auth_headers):
    guardian = register_user()
    dependent = register_user(role="DEPENDENT", mode="MEMORY_SUPPORT")
    other_dependent = register_user(role="DEPENDENT")
    unrelated_guardian = register_user()
    guardian_headers = auth_headers(guardian["access_token"])
    dependent_headers = auth_headers(dependent["access_token"])
    dependent_id = dependent["user"]["id"]

    link = client.post("/api/v1/guardian/links", headers=guardian_headers,
                       json={"dependent_email": dependent["user"]["email"]})
    assert link.status_code == 201, link.text
    approved = client.post(
        f"/api/v1/dependent/links/{link.json()['id']}/accept",
        headers=dependent_headers,
        json={"granted_categories": ["wellbeing"]},
    )
    assert approved.status_code == 200, approved.text

    question_response = client.get(f"/api/v1/dependents/{dependent_id}/wellbeing/questions", headers=dependent_headers)
    assert question_response.status_code == 200
    assert all("scores" not in choice for question in question_response.json() for choice in question["choices"])
    answers = {question["id"]: question["choices"][0]["id"] for question in question_response.json()}

    assert client.get(f"/api/v1/dependents/{dependent_id}/wellbeing/today", headers=dependent_headers).json()["completed"] is False
    submitted = client.post(f"/api/v1/dependents/{dependent_id}/wellbeing-checkins", headers=dependent_headers, json={"answers": answers})
    assert submitted.status_code == 201, submitted.text
    assert submitted.json()["completed"] is True
    assert submitted.json()["result"]["overall_score"] is not None
    assert submitted.json()["result"]["answers"][0]["answer"]

    duplicate = client.post(f"/api/v1/dependents/{dependent_id}/wellbeing-checkins", headers=dependent_headers, json={"answers": answers})
    assert duplicate.status_code == 409
    assert client.get(f"/api/v1/dependents/{dependent_id}/wellbeing/today", headers=dependent_headers).json()["completed"] is True
    assert client.get(f"/api/v1/dependents/{dependent_id}/wellbeing/today", headers=auth_headers(unrelated_guardian["access_token"])).status_code == 404
    assert client.get(f"/api/v1/dependents/{dependent_id}/wellbeing/report", headers=auth_headers(other_dependent["access_token"])).status_code == 403
    assert client.post(f"/api/v1/dependents/{dependent_id}/wellbeing-checkins", headers=guardian_headers, json={"answers": answers}).status_code == 403

    report = client.get(f"/api/v1/dependents/{dependent_id}/wellbeing/report", headers=guardian_headers)
    assert report.status_code == 200, report.text
    assert report.json()["today_result"]["overall_category"]
    assert report.json()["today_result"]["answers"]
    assert report.json()["completed_checkins"] == 1
    assert "category_trends" in report.json()
    assert client.get(f"/api/v1/dependents/{dependent_id}/wellbeing/report", headers=auth_headers(unrelated_guardian["access_token"])).status_code == 404

    reset = client.post(f"/api/v1/dependents/{dependent_id}/wellbeing/today/reset", headers=guardian_headers)
    assert reset.status_code == 200, reset.text
    assert client.get(f"/api/v1/dependents/{dependent_id}/wellbeing/today", headers=dependent_headers).json()["completed"] is False
    history = client.get(f"/api/v1/dependents/{dependent_id}/wellbeing-checkins", headers=dependent_headers)
    assert history.status_code == 200 and len(history.json()) == 1
    assert history.json()[0]["overall_category"]
    reset_report = client.get(f"/api/v1/dependents/{dependent_id}/wellbeing/report", headers=guardian_headers)
    assert reset_report.json()["today_result"] is None
    assert reset_report.json()["completed_checkins"] == 1
    assert len(reset_report.json()["history"]) == 1
    assert client.post(f"/api/v1/dependents/{dependent_id}/wellbeing-checkins", headers=dependent_headers, json={"answers": answers}).status_code == 201
    after_resubmit = client.get(f"/api/v1/dependents/{dependent_id}/wellbeing/report", headers=guardian_headers)
    assert after_resubmit.json()["completed_checkins"] == 2
    assert len(after_resubmit.json()["history"]) == 2


def test_casual_game_sessions_are_general_and_scoped(client, register_user, auth_headers):
    dependent = register_user(role="DEPENDENT")
    dependent_id = dependent["user"]["id"]
    headers = auth_headers(dependent["access_token"])
    guardian = register_user()
    guardian_headers = auth_headers(guardian["access_token"])

    denied = client.post(f"/api/v1/dependents/{dependent_id}/game-sessions", headers=guardian_headers, json={"game_type": "matching_pairs"})
    assert denied.status_code == 403
    invalid = client.post(f"/api/v1/dependents/{dependent_id}/game-sessions", headers=headers, json={"game_type": "family_match"})
    assert invalid.status_code == 422

    expected_games = {
        "sequence_memory": "Sequence Memory",
        "tile_memory": "Tile Memory",
        "pattern_memory": "Pattern Memory",
        "matching_pairs": "Matching Pairs",
        "odd_one_out": "Odd One Out",
    }
    started_sessions = {}
    for game_type, title in expected_games.items():
        started = client.post(
            f"/api/v1/dependents/{dependent_id}/game-sessions",
            headers=headers,
            json={"game_type": game_type},
        )
        assert started.status_code == 201, started.text
        assert started.json()["title"] == title
        started_sessions[game_type] = started.json()["id"]

    game = client.get(f"/api/v1/dependents/{dependent_id}/games", headers=headers)
    assert game.status_code == 200
    assert {row["title"] for row in game.json()} == set(expected_games.values())
    assert all(row["configuration"]["kind"] == "general" for row in game.json())
    for session_id in started_sessions.values():
        completed = client.post(
            f"/api/v1/game-sessions/{session_id}/finish",
            headers=headers,
            json={"interactions": 8, "result": {"rounds_completed": 3, "score": 30, "completed": True}},
        )
        assert completed.status_code == 200, completed.text


def test_linked_guardian_without_wellbeing_grant_cannot_read_or_reset_checkin(
    client, register_user, auth_headers
):
    guardian = register_user()
    dependent = register_user(role="DEPENDENT")
    guardian_headers = auth_headers(guardian["access_token"])
    dependent_headers = auth_headers(dependent["access_token"])
    dependent_id = dependent["user"]["id"]

    link = client.post(
        "/api/v1/guardian/links",
        headers=guardian_headers,
        json={"dependent_email": dependent["user"]["email"]},
    )
    assert link.status_code == 201, link.text
    accepted = client.post(
        f"/api/v1/dependent/links/{link.json()['id']}/accept",
        headers=dependent_headers,
        json={"granted_categories": ["profile"]},
    )
    assert accepted.status_code == 200, accepted.text

    assert client.get(
        f"/api/v1/dependents/{dependent_id}/wellbeing/report", headers=guardian_headers
    ).status_code == 403
    assert client.post(
        f"/api/v1/dependents/{dependent_id}/wellbeing/today/reset", headers=guardian_headers
    ).status_code == 403
