from datetime import datetime
from typing import Dict, List
from dateutil.relativedelta import relativedelta
import logging
from fastapi import BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64
import json

import app.utils.flow_utils as futil
import app.database.db as db
from app.database.models import User
from app.services.whatsapp_service import whatsapp_client
from app.config import settings
from app.utils.string_manager import StringCategory, strings
import app.database.enums as enums
import scripts.flows.designing_flows as flows_wip

logger = logging.getLogger(__name__)


class FlowService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.data_exchange_action_handlers: Dict[str, callable] = {
            settings.onboarding_flow_id: self.handle_onboarding_data_exchange_action,
            settings.select_subjects_flow_id: self.handle_subject_data_exchange_action,
            settings.select_classes_flow_id: self.handle_classes_data_exchange_action,
        }

        # NOTE: This is only used when designing flows (i.e. work-in-progress)
        self.init_action_handlers: Dict[str, callable] = {
            settings.onboarding_flow_id: flows_wip.handle_onboarding_init_action,
            settings.select_subjects_flow_id: flows_wip.handle_select_subjects_init_action,
            settings.select_classes_flow_id: flows_wip.handle_select_classes_init_action,
        }

    async def handle_flow_request(
        self, body: dict, bg_tasks: BackgroundTasks
    ) -> PlainTextResponse:
        try:
            payload, aes_key, initial_vector = await futil.decrypt_flow_request(body)
            action = payload.get("action")
            flow_token = payload.get("flow_token")

            if action == "ping":
                return await flow_client.handle_health_check(aes_key, initial_vector)

            if not flow_token:
                self.logger.error("Missing flow token")
                return PlainTextResponse(
                    content={
                        "error_msg": "Missing flow token, Unable to process request"
                    },
                    status_code=422,
                )

            # Get the user and flow ID
            wa_id, flow_id = futil.decrypt_flow_token(flow_token)
            user = await db.get_user_by_waid(wa_id)

            if not user:
                self.logger.error(f"User not found for WA ID: {wa_id}")
                raise ValueError("User not found")

            if action == "data_exchange":
                handler = flow_client.data_exchange_action_handlers.get(
                    flow_id, flow_client.handle_unknown_flow
                )
                return await handler(user, payload, aes_key, initial_vector, bg_tasks)
            elif action == "INIT":
                self.logger.warning(f"WIP Flow is being processed: {flow_id}")
                handler = flow_client.init_action_handlers.get(
                    flow_id, flow_client.handle_unknown_flow
                )
                response_payload = await handler(user)
                return await self.process_response(
                    response_payload, aes_key, initial_vector
                )
            else:
                return await flow_client.handle_unknown_action(
                    user, payload, aes_key, initial_vector
                )
        except ValueError as e:
            self.logger.error(f"Error decrypting payload: {e}")
            return PlainTextResponse(content="Decryption failed", status_code=421)
        except futil.FlowTokenError as e:
            self.logger.error(f"Error decrypting flow token: {e}")
            return PlainTextResponse(
                content={"error_msg": "Your request has expired please start again"},
                status_code=422,
            )
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return PlainTextResponse(content="Decryption failed", status_code=500)

    async def handle_unknown_flow(
        self,
        user: User,
        payload: dict,
        aes_key: bytes,
        initial_vector: str,
        **kwargs,
    ) -> PlainTextResponse:
        self.logger.warning(f"Unknown flow received: {payload.get('flow_id')}")
        response_payload = {"unknown": "flow"}
        return await self.process_response(response_payload, aes_key, initial_vector)

    async def handle_unknown_action(
        self, user: User, payload: dict, aes_key: bytes, initial_vector: str
    ) -> PlainTextResponse:
        self.logger.warning(f"Unknown action received: {payload.get('action')}")
        response_payload = {"unknown": "event"}
        return await self.process_response(response_payload, aes_key, initial_vector)

    async def handle_onboarding_data_exchange_action(
        self,
        user: User,
        payload: dict,
        aes_key: bytes,
        initial_vector: str,
        background_tasks: BackgroundTasks,
    ) -> PlainTextResponse:
        try:
            self.logger.debug(f"Handling onboarding data exchange: {payload}")
            data = payload.get("data", {})
            is_update = data.get("is_updating", False)
            encrypted_flow_token = payload.get("flow_token")

            # TODO: Determine if this can be run as a background task or not
            background_tasks.add_task(
                self.update_onboarding_data_background, user, data, is_update
            )

            response_payload = futil.create_flow_response_payload(
                screen="SUCCESS",
                data={},
                encrypted_flow_token=encrypted_flow_token,
            )
            return await self.process_response(
                response_payload, aes_key, initial_vector
            )
        except ValueError as e:
            return PlainTextResponse(content={"error_msg": str(e)}, status_code=422)
        except Exception as e:
            return PlainTextResponse(content={"error_msg": str(e)}, status_code=500)

    async def handle_subject_data_exchange_action(
        self,
        user: User,
        payload: dict,
        aes_key: bytes,
        initial_vector: str,
        background_tasks: BackgroundTasks,
    ) -> PlainTextResponse:
        try:
            self.logger.info(f"Handling subject class info data exchange: {payload}")
            data = payload.get("data", {})
            selected_subject_ids = [int(id) for id in data.get("selected_subjects", [])]
            encrypted_flow_token = payload.get("flow_token")

            if not selected_subject_ids:
                self.logger.error("No subjects selected")
                raise ValueError("No subjects selected")

            # TODO: What about is_updating?
            background_tasks.add_task(
                self.update_subject_data_background, user, selected_subject_ids
            )

            response_payload = futil.create_flow_response_payload(
                screen="SUCCESS", data={}, encrypted_flow_token=encrypted_flow_token
            )

            return await self.process_response(
                response_payload, aes_key, initial_vector
            )

        except ValueError as e:
            return PlainTextResponse(content={"error_msg": str(e)}, status_code=422)
        except Exception as e:
            return PlainTextResponse(content={"error_msg": str(e)}, status_code=500)

    async def handle_classes_data_exchange_action(
        self,
        user: User,
        payload: dict,
        aes_key: bytes,
        initial_vector: str,
        background_tasks: BackgroundTasks,
    ) -> PlainTextResponse:
        try:
            self.logger.info(f"Handling classes data exchange: {payload}")
            data = payload.get("data", {})
            selected_classes = [int(id) for id in data.get("selected_classes", [])]
            subject_id = int(data.get("subject_id"))  # This may raise an error
            encrypted_flow_token = payload.get("flow_token")

            if not selected_classes:
                self.logger.error("No classes selected")
                raise ValueError("No classes selected")

            background_tasks.add_task(
                self.update_user_classes_data_background,
                user,
                selected_classes,
                subject_id,
            )

            response_payload = futil.create_flow_response_payload(
                screen="SUCCESS", data={}, encrypted_flow_token=encrypted_flow_token
            )
            return await self.process_response(
                response_payload, aes_key, initial_vector
            )

        except ValueError as e:
            return JSONResponse(content={"error_msg": str(e)}, status_code=422)
        except Exception as e:
            return PlainTextResponse(content={"error_msg": str(e)}, status_code=500)

    async def update_onboarding_data_background(
        self, user: User, data: dict, is_updating: bool
    ):
        try:
            full_name = (
                data.get("update_full_name") if is_updating else data.get("full_name")
            )
            birthday = (
                data.get("update_birthday") if is_updating else data.get("birthday")
            )
            region = data.get("update_region") if is_updating else data.get("region")
            school_name = (
                data.get("update_school_name")
                if is_updating
                else data.get("school_name")
            )
            user.name = full_name or user.name
            user.birthday = (
                datetime.strptime(birthday, "%Y-%m-%d") if birthday else None
            )
            user.region = region
            user.school_name = school_name
            user.onboarding_state = "personal_info_submitted"
            await db.update_user(user)
            self.logger.info(f"User after update: {user}")

            # send select subject flow
            if not is_updating:
                await self.send_select_subject_flow(user)
        except Exception as e:
            await whatsapp_client.send_message(
                user.wa_id, strings.get_string(StringCategory.ERROR, "general")
            )
            self.logger.error(f"Failed to update onboarding data: {str(e)}")

    async def update_subject_data_background(
        self, user: User, selected_subject_ids: List[int], is_updating: bool = False
    ):
        try:
            # NOTE: Instead of partially updating the users class_info, we send the select classes flows and update it that way
            # TODO: Replace this with a single flow being sent
            for subject_id in selected_subject_ids:
                await self.send_select_classes_flow(user, subject_id)
        except Exception as e:
            await whatsapp_client.send_message(
                user.wa_id, strings.get_string(StringCategory.ERROR, "general")
            )
            self.logger.error(f"Failed to update subject data: {str(e)}")

    async def update_user_classes_data_background(
        self, user: User, selected_classes: List[int], subject_id: int
    ):
        try:
            # Update user classes in the database
            # TODO: Replace this with a different function
            # user = await db.update_user_selected_classes(
            #     user, selected_classes, subject_id
            # )

            self.logger.info(
                f"FINAL User after update: {user}, Selected classes: {selected_classes}"
            )

            # send message to user saying that the class info has been submitted
            responseText = "Thanks for submitting your subject and classes information. How can I help you today?"
            await whatsapp_client.send_message(user.wa_id, responseText)

        except Exception as e:
            responseText = "An error occurred during the onboarding process. Please try again later."
            await whatsapp_client.send_message(user.wa_id, responseText)
            self.logger.error(f"Failed to update user subject classes: {str(e)}")

    async def handle_health_check(
        self, aes_key: bytes, initial_vector: str
    ) -> PlainTextResponse:
        self.logger.debug("Received flow health check event ❤️‍🩹")
        response_payload = {"data": {"status": "active"}}
        return await self.process_response(response_payload, aes_key, initial_vector)

    async def process_response(
        self, response_payload: dict, aes_key: bytes, initial_vector: str
    ) -> PlainTextResponse:
        self.logger.info(
            f"Processing response: {response_payload} , AES Key: {aes_key} , IV: {initial_vector}"
        )

        try:
            response_bytes = json.dumps(response_payload).encode("utf-8")

            iv_bytes = base64.b64decode(initial_vector)
            inverted_iv_bytes = bytes(~b & 0xFF for b in iv_bytes)

            encryptor = Cipher(
                algorithms.AES(aes_key),
                modes.GCM(inverted_iv_bytes),
                backend=default_backend(),
            ).encryptor()
            encrypted_data = encryptor.update(response_bytes) + encryptor.finalize()
            encrypted_data_tag = encryptor.tag
            encrypted_data_bytes = encrypted_data + encrypted_data_tag

            encrypted_response = base64.b64encode(encrypted_data_bytes).decode("utf-8")
            self.logger.info(f"Encrypted response: {encrypted_response}")

            return PlainTextResponse(content=encrypted_response, status_code=200)
        except Exception as e:
            self.logger.error(f"Error encrypting response: {e}")
            return PlainTextResponse(content="Encryption failed", status_code=500)

    async def send_user_settings_flow(self, user: User) -> None:
        flow_strings = strings.get_category(StringCategory.FLOWS)
        header_text = flow_strings["personal_settings_header"]
        body_text = flow_strings["personal_settings_body"]
        data = {
            "full_name": user.name or "Name",
            "min_date": "1900-01-01",
            "max_date": (datetime.now() - relativedelta(years=18)).strftime("%Y-%m-%d"),
            "is_updating": True,
            "region": user.region,
            # TODO: what if the birthday is None?
            "birthday": user.birthday.strftime("%Y-%m-%d"),
            "school_name": user.school_name,
        }
        await futil.send_whatsapp_flow_message(
            user=user,
            flow_id=settings.onboarding_flow_id,
            header_text=header_text,
            body_text=body_text,
            action_payload={
                "screen": "personal_info",
                "data": data,
            },
            flow_cta=flow_strings["personal_settings_cta"],
        )

    async def send_personal_and_school_info_flow(self, user: User) -> None:
        flow_strings = strings.get_category(StringCategory.FLOWS)
        header_text = flow_strings["start_onboarding_header"]
        body_text = flow_strings["start_onboarding_body"]
        data = {
            "full_name": user.name or "Name",
            "min_date": "1900-01-01",
            "max_date": (datetime.now() - relativedelta(years=18)).strftime("%Y-%m-%d"),
            "is_updating": False,
        }
        await futil.send_whatsapp_flow_message(
            user=user,
            flow_id=settings.onboarding_flow_id,
            header_text=header_text,
            body_text=body_text,
            action_payload={
                "screen": "personal_info",
                "data": data,
            },
            flow_cta=flow_strings["start_onboarding_cta"],
        )

    # The same flow is sent for both settings and onboarding
    async def send_select_subject_flow(self, user: User) -> None:
        subjects = await db.get_available_subjects()
        formatted_subjects = [
            {
                "id": subject["id"],
                "title": enums.SubjectName(subject["title"]).title_format,
            }
            for subject in subjects
        ]

        flow_strings = strings.get_category(StringCategory.FLOWS)

        if len(formatted_subjects) == 0:
            await whatsapp_client.send_message(
                user.wa_id,
                strings.get_string(StringCategory.ERROR, "no_available_subjects"),
            )
            return

        header_text = flow_strings["subjects_flow_header"]
        body_text = flow_strings["subjects_flow_body"]

        # TODO: Leave this for now, discuss with Fredy if its necessary
        response_payload = futil.create_flow_response_payload(
            screen="select_subjects",
            data={
                "subjects": formatted_subjects,
                "has_subjects": True,
                "no_subjects_text": "",  # TODO: We don't need this
                "select_subject_text": flow_strings["select_subjects_text"],
            },
        )
        await futil.send_whatsapp_flow_message(
            user=user,
            flow_id=settings.select_subjects_flow_id,
            header_text=header_text,
            body_text=body_text,
            action_payload=response_payload,
            flow_cta=flow_strings["subjects_flow_cta"],
        )

    # The same flow is sent for both settings and onboarding
    async def send_select_classes_flow(
        self, user: User, subject_id: int, is_update: bool = False
    ) -> None:
        try:
            # TODO: Make this possible for multiple subjects
            subject_data = await db.get_subject_grade_levels(subject_id)

            subject_title = enums.SubjectName(subject_data["subject_name"]).title_format
            classes = subject_data["classes"]
            self.logger.warning("made it her")

            flow_strings = strings.get_category(StringCategory.FLOWS)

            header_text = flow_strings["classes_flow_header"].format(
                subject=subject_title
            )
            self.logger.warning("made it her 2")
            body_text = flow_strings["classes_flow_body"]

            self.logger.warning("made it her3")
            response_payload = futil.create_flow_response_payload(
                screen="select_classes",
                data=futil.create_subject_class_payload(
                    subject_title=subject_title,
                    classes=classes,
                    is_update=is_update,
                    subject_id=str(subject_id),
                ),
            )

            await futil.send_whatsapp_flow_message(
                user=user,
                flow_id=settings.select_classes_flow_id,
                header_text=header_text,
                body_text=body_text,
                action_payload=response_payload,
                flow_cta=flow_strings["classes_flow_cta"],
            )
        except Exception as e:
            self.logger.error(f"Error sending select classes flow: {e}")
            raise


flow_client = FlowService()
