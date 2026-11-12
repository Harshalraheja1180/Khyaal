from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.entities import AuditLog, MemoryObject, MemoryPerson, MemoryPlace, OrientationActivity, Quiz, QuizAttempt, QuizOption, QuizQuestion, User
from app.schemas.api import MemoryEntryCreate, MemoryEntryUpdate, QuizAnswerCreate, QuizCreate, QuizOptionCreate, QuizOptionUpdate, QuizOut, QuizQuestionCreate, QuizQuestionUpdate, QuizUpdate
from app.services.authorization import has_role, require_dependent_access

router = APIRouter(tags=["memory activities"])


@router.get("/dependents/{dependent_id}/memory/{entry_type}")
def list_memory_entries(dependent_id: UUID, entry_type: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    require_dependent_access(db, current, dependent_id, "profile")
    models = {"people": MemoryPerson, "places": MemoryPlace, "objects": MemoryObject}
    model = models.get(entry_type)
    if model is None:
        raise HTTPException(status_code=404, detail="Unknown memory entry type")
    entries = db.scalars(select(model).where(model.dependent_id == dependent_id).order_by(model.created_at.desc())).all()
    return [{"id": str(item.id), "dependent_id": str(item.dependent_id), "name": item.name,
             "description": getattr(item, "description", None), "relationship_label": getattr(item, "relationship_label", None),
             "media_id": str(item.media_id) if item.media_id else None} for item in entries]


@router.post("/dependents/{dependent_id}/memory/{entry_type}", status_code=201)
def create_memory_entry(dependent_id: UUID, entry_type: str, payload: MemoryEntryCreate,
                        current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    require_dependent_access(db, current, dependent_id, "profile")
    models = {"people": MemoryPerson, "places": MemoryPlace, "objects": MemoryObject}
    model = models.get(entry_type)
    if model is None:
        raise HTTPException(status_code=404, detail="Unknown memory entry type")
    if payload.media_id:
        from app.models.entities import MediaAsset
        asset = db.get(MediaAsset, payload.media_id)
        if not asset or asset.dependent_id != dependent_id:
            raise HTTPException(status_code=404, detail="Media not found for this dependent")
    fields = {"dependent_id": dependent_id, "name": payload.name, "media_id": payload.media_id}
    if entry_type == "people":
        fields["relationship_label"] = payload.relationship_label
    else:
        fields["description"] = payload.description
    item = model(**fields)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": str(item.id), "name": item.name}


@router.patch("/memory-entries/{entry_type}/{entry_id}")
def update_memory_entry(entry_type: str, entry_id: UUID, payload: MemoryEntryUpdate,
                        current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    models = {"people": MemoryPerson, "places": MemoryPlace, "objects": MemoryObject}
    model = models.get(entry_type)
    if model is None:
        raise HTTPException(status_code=404, detail="Unknown memory entry type")
    item = db.get(model, entry_id)
    if not item:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    require_dependent_access(db, current, item.dependent_id, "profile")
    updates = payload.model_dump(exclude_unset=True)
    if payload.media_id:
        from app.models.entities import MediaAsset
        asset = db.get(MediaAsset, payload.media_id)
        if not asset or asset.dependent_id != item.dependent_id:
            raise HTTPException(status_code=404, detail="Media not found for this dependent")
    allowed_fields = {"people": {"name", "relationship_label", "media_id"},
                      "places": {"name", "description", "media_id"},
                      "objects": {"name", "description", "media_id"}}[entry_type]
    for key, value in updates.items():
        if key in allowed_fields:
            setattr(item, key, value)
    db.commit()
    return {"id": str(item.id), "name": item.name}


@router.delete("/memory-entries/{entry_type}/{entry_id}", status_code=204)
def delete_memory_entry(entry_type: str, entry_id: UUID, current: User = Depends(get_current_user),
                        db: Session = Depends(get_db)) -> Response:
    model = {"people": MemoryPerson, "places": MemoryPlace, "objects": MemoryObject}.get(entry_type)
    if model is None:
        raise HTTPException(status_code=404, detail="Unknown memory entry type")
    item = db.get(model, entry_id)
    if not item:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    require_dependent_access(db, current, item.dependent_id, "profile")
    db.delete(item)
    db.commit()
    return Response(status_code=204)


@router.get("/dependents/{dependent_id}/quizzes", response_model=list[QuizOut])
def list_quizzes(dependent_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Quiz]:
    require_dependent_access(db, current, dependent_id, "profile")
    statement = select(Quiz).where(Quiz.dependent_id == dependent_id)
    if not has_role(db, current, "GUARDIAN"):
        statement = statement.where(Quiz.active.is_(True))
    return list(db.scalars(statement.order_by(Quiz.created_at.desc())).all())


@router.post("/dependents/{dependent_id}/quizzes", response_model=QuizOut, status_code=201)
def create_quiz(dependent_id: UUID, payload: QuizCreate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Quiz:
    require_dependent_access(db, current, dependent_id, "profile")
    quiz = Quiz(dependent_id=dependent_id, title=payload.title, difficulty=payload.difficulty, active=False)
    db.add(quiz)
    db.flush()
    db.add(AuditLog(actor_id=current.id, action="quiz.create", resource_type="quiz", resource_id=str(quiz.id), dependent_id=dependent_id))
    db.commit()
    db.refresh(quiz)
    return quiz


@router.patch("/quizzes/{quiz_id}", response_model=QuizOut)
def update_quiz(quiz_id: UUID, payload: QuizUpdate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Quiz:
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    require_dependent_access(db, current, quiz.dependent_id, "profile")
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("active") is True:
        questions = db.scalars(select(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id)).all()
        if not questions:
            raise HTTPException(status_code=422, detail="Add at least one complete question before activating this quiz")
        for question in questions:
            options = db.scalars(select(QuizOption).where(QuizOption.question_id == question.id)).all()
            if len(options) < 2 or len(options) > 4 or sum(option.is_correct for option in options) != 1:
                raise HTTPException(status_code=422, detail="Each question needs 2 to 4 answers and one correct choice")
    for key, value in updates.items():
        setattr(quiz, key, value)
    db.commit()
    db.refresh(quiz)
    return quiz


@router.delete("/quizzes/{quiz_id}", status_code=204)
def delete_quiz(quiz_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    require_dependent_access(db, current, quiz.dependent_id, "profile")
    db.delete(quiz)
    db.commit()
    return Response(status_code=204)


@router.get("/quizzes/{quiz_id}/detail")
def quiz_detail(quiz_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    require_dependent_access(db, current, quiz.dependent_id, "profile")
    guardian = has_role(db, current, "GUARDIAN")
    questions = db.scalars(select(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id).order_by(QuizQuestion.position)).all()
    nested = []
    for question in questions:
        options = db.scalars(select(QuizOption).where(QuizOption.question_id == question.id).order_by(QuizOption.position)).all()
        nested.append({"id": str(question.id), "prompt": question.prompt, "image_media_id": str(question.image_media_id) if question.image_media_id else None,
                       "audio_media_id": str(question.audio_media_id) if question.audio_media_id else None, "position": question.position,
                       "options": [{"id": str(option.id), "label": option.label, "image_media_id": str(option.image_media_id) if option.image_media_id else None,
                                    "position": option.position, **({"is_correct": option.is_correct} if guardian else {})} for option in options]})
    return {"id": str(quiz.id), "dependent_id": str(quiz.dependent_id), "title": quiz.title, "difficulty": quiz.difficulty, "active": quiz.active, "questions": nested}


@router.post("/quizzes/{quiz_id}/questions", status_code=201)
def create_quiz_question(quiz_id: UUID, payload: QuizQuestionCreate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    require_dependent_access(db, current, quiz.dependent_id, "profile")
    _validate_quiz_media(db, quiz.dependent_id, payload.image_media_id, payload.audio_media_id)
    quiz.active = False
    question = QuizQuestion(quiz_id=quiz.id, **payload.model_dump())
    db.add(question)
    db.commit()
    db.refresh(question)
    return {"id": str(question.id), "prompt": question.prompt}


@router.patch("/quiz-questions/{question_id}")
def update_quiz_question(question_id: UUID, payload: QuizQuestionUpdate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    question = db.get(QuizQuestion, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    quiz = db.get(Quiz, question.quiz_id)
    require_dependent_access(db, current, quiz.dependent_id, "profile")
    updates = payload.model_dump(exclude_unset=True)
    _validate_quiz_media(db, quiz.dependent_id, updates.get("image_media_id"), updates.get("audio_media_id"))
    quiz.active = False
    for key, value in updates.items():
        setattr(question, key, value)
    db.commit()
    return {"id": str(question.id), "prompt": question.prompt}


@router.delete("/quiz-questions/{question_id}", status_code=204)
def delete_quiz_question(question_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    question = db.get(QuizQuestion, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    quiz = db.get(Quiz, question.quiz_id)
    require_dependent_access(db, current, quiz.dependent_id, "profile")
    quiz.active = False
    db.delete(question)
    db.commit()
    return Response(status_code=204)


@router.post("/quiz-questions/{question_id}/options", status_code=201)
def create_quiz_option(question_id: UUID, payload: QuizOptionCreate,
                       current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    question = db.get(QuizQuestion, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    quiz = db.get(Quiz, question.quiz_id)
    require_dependent_access(db, current, quiz.dependent_id, "profile")
    existing = db.scalars(select(QuizOption).where(QuizOption.question_id == question.id)).all()
    if len(existing) >= 4:
        raise HTTPException(status_code=422, detail="A question can have at most four answer choices")
    _validate_quiz_media(db, quiz.dependent_id, payload.image_media_id)
    if payload.is_correct:
        for other in existing:
            other.is_correct = False
    quiz.active = False
    option = QuizOption(question_id=question.id, **payload.model_dump())
    db.add(option)
    db.commit()
    db.refresh(option)
    return {"id": str(option.id), "label": option.label}


@router.patch("/quiz-options/{option_id}")
def update_quiz_option(option_id: UUID, payload: QuizOptionUpdate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    option = db.get(QuizOption, option_id)
    if not option:
        raise HTTPException(status_code=404, detail="Option not found")
    question = db.get(QuizQuestion, option.question_id)
    quiz = db.get(Quiz, question.quiz_id)
    require_dependent_access(db, current, quiz.dependent_id, "profile")
    updates = payload.model_dump(exclude_unset=True)
    _validate_quiz_media(db, quiz.dependent_id, updates.get("image_media_id"))
    if updates.get("is_correct"):
        for other in db.scalars(select(QuizOption).where(QuizOption.question_id == question.id, QuizOption.id != option.id)).all():
            other.is_correct = False
    for key, value in updates.items():
        setattr(option, key, value)
    db.commit()
    return {"id": str(option.id), "label": option.label}


@router.delete("/quiz-options/{option_id}", status_code=204)
def delete_quiz_option(option_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    option = db.get(QuizOption, option_id)
    if not option:
        raise HTTPException(status_code=404, detail="Option not found")
    question = db.get(QuizQuestion, option.question_id)
    quiz = db.get(Quiz, question.quiz_id)
    require_dependent_access(db, current, quiz.dependent_id, "profile")
    quiz.active = False
    db.delete(option)
    db.commit()
    return Response(status_code=204)


def _validate_quiz_media(db: Session, dependent_id: UUID, *media_ids: UUID | None) -> None:
    from app.models.entities import MediaAsset
    for media_id in media_ids:
        if media_id is None:
            continue
        asset = db.get(MediaAsset, media_id)
        if not asset or asset.dependent_id != dependent_id:
            raise HTTPException(status_code=404, detail="Quiz media not found for this dependent")


@router.post("/quiz-questions/{question_id}/answer")
def answer_quiz_question(question_id: UUID, payload: QuizAnswerCreate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    question = db.get(QuizQuestion, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    quiz = db.get(Quiz, question.quiz_id)
    if not quiz.active:
        raise HTTPException(status_code=404, detail="Quiz is not active")
    if current.id != quiz.dependent_id:
        raise HTTPException(status_code=403, detail="Only the dependent can answer this quiz")
    option = db.get(QuizOption, payload.option_id)
    if not option or option.question_id != question.id:
        raise HTTPException(status_code=422, detail="Choose an answer from this question")
    attempt = QuizAttempt(quiz_id=quiz.id, question_id=question.id, dependent_id=current.id,
                          selected_option_id=option.id, is_correct=option.is_correct)
    db.add(attempt)
    db.commit()
    return {"correct": option.is_correct, "message": "That's right. Well done!" if option.is_correct else "Thank you for trying. Let's take another gentle look."}


@router.get("/dependents/{dependent_id}/orientation-activities")
def list_orientation_activities(dependent_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    require_dependent_access(db, current, dependent_id, "profile")
    items = db.scalars(select(OrientationActivity).where(OrientationActivity.dependent_id == dependent_id, OrientationActivity.active.is_(True))).all()
    return [{"id": str(item.id), "title": item.title, "prompt": item.prompt, "configuration": item.configuration} for item in items]


@router.post("/dependents/{dependent_id}/orientation-activities", status_code=201)
def create_orientation_activity(dependent_id: UUID, title: str, prompt: str,
                                current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    require_dependent_access(db, current, dependent_id, "profile")
    activity = OrientationActivity(dependent_id=dependent_id, title=title[:160], prompt=prompt[:500])
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return {"id": str(activity.id), "title": activity.title}
