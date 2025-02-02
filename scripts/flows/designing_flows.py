from typing import Any, Dict
from fastapi.responses import PlainTextResponse
import logging

from app.database import db
from app.database.models import User
import app.utils.flow_utils as futil

logger = logging.getLogger(__name__)


async def handle_onboarding_init_action(
    user: User,
) -> Dict[str, Any] | PlainTextResponse:
    try:
        response_payload = futil.create_flow_response_payload(
            screen="personal_info",
            data={
                "full_name": user.name,
            },
        )
        return response_payload
    except ValueError as e:
        return PlainTextResponse(content={"error_msg": str(e)}, status_code=422)


async def handle_subjects_classes_init_action(
    user: User,
) -> Dict[str, Any] | PlainTextResponse:
    try:
        # Fetch available subjects with their classes from the database
        subjects = await db.read_subjects()
        logger.debug(f"Available subjects with classes: {subjects}")

        subjects_data = {}
        if subjects is None:
            subjects = []
        for i, subject in enumerate(subjects, start=1):
            subject_id = subject.id
            subject_title = subject.name
            classes = await db.read_subjects()
            subjects_data[f"subject{i}"] = {
                "subject_id": str(subject_id),
                "subject_title": subject_title,
                "classes": [
                    {"id": str(cls.id), "title": cls.name} for cls in classes or []
                ],
                "available": len(classes or []) > 0,
                "label": f"Classes for {subject_title}",
            }
            subjects_data[f"subject{i}_available"] = len(classes or []) > 0
            subjects_data[f"subject{i}_label"] = f"Classes for {subject_title}"

        # Prepare the response payload
        response_payload = futil.create_flow_response_payload(
            screen="select_subjects_and_classes",
            data={
                **subjects_data,
                "select_subject_text": "Please select the subjects and the classes you teach.",
                "no_subjects_text": "Sorry, there are no available subjects.",
            },
        )

        return response_payload

    except ValueError as e:
        return PlainTextResponse(content={"error_msg": str(e)}, status_code=422)
