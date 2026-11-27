from uuid import UUID

import sentry_sdk
import sentry_sdk.logger as sentry_logger

from app.api.models.statutory_rules import StatutoryRule
from app.api.models.user import User
from app.api.repo.statutory_rules import StatutoryRuleRepository
from app.api.schemas.statutory_rules import (
    StatutoryRuleCreate,
    StatutoryRuleInDB,
    StatutoryRuleListQuery,
    StatutoryRuleResponse,
)
from app.api.schemas.user import CachedUser
from app.core.exceptions import EntityExistsError, NotFoundError, ServerError


class StatutoryRuleService:
    def __init__(self, statutory_rule_repo: StatutoryRuleRepository):
        self._statutory_rule_repo = statutory_rule_repo

    async def get_statutory_rules(
        self, list_query: StatutoryRuleListQuery
    ) -> tuple[list[StatutoryRuleResponse], str | None]:
        try:
            records: dict = await self._statutory_rule_repo.get_statutory_rules(
                list_query
            )

            cursor, rules = records.get("cursor"), records.get("data")

            if not rules:
                sentry_logger.warning("Statutory rules not found")
                raise NotFoundError(entity="Statutory rules")

            sentry_logger.info("Statutory rules retrieved")
            return [
                StatutoryRuleResponse.model_validate(rule) for rule in rules
            ], cursor
        except NotFoundError:
            raise
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error("Error occurred while retrieving statutory rules")
            raise ServerError() from exc

    async def get_statutory_rule(self, rule_id: UUID) -> StatutoryRuleResponse:
        try:
            rule: StatutoryRule | None = await self._statutory_rule_repo.get_record(
                id=rule_id
            )

            if not rule:
                sentry_logger.warning(
                    "Statutory rule not found with id {rule_id}", rule_id=rule_id
                )
                raise NotFoundError(entity="Statutory rule")

            sentry_logger.info("Statutory rule {rule_id} retrieved", rule_id=rule_id)
            return StatutoryRuleResponse.model_validate(rule)
        except NotFoundError:
            raise
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while retrieving statutory rule {rule_id}",
                rule_id=rule_id,
            )
            raise ServerError() from exc

    async def create_statutory_rule(
        self, curr_user: User | CachedUser, statutory_rule: StatutoryRuleCreate
    ) -> StatutoryRuleResponse:
        try:
            rule_in_db = StatutoryRuleInDB(
                created_by=curr_user.id, **statutory_rule.model_dump()
            )

            rule_db: StatutoryRule | None = (
                await self._statutory_rule_repo.create_statutory_rule(rule_in_db)
            )

            if not rule_db:
                sentry_logger.warning(
                    "Statutory rule with effective_from {effective_from} "
                    "already exists",
                    effective_from=statutory_rule.effective_from,
                )
                raise EntityExistsError(
                    entity="Statutory rule",
                    entity_property="effective_from",
                    entity_value=str(statutory_rule.effective_from),
                )

            await self._statutory_rule_repo.commit()
            await self._statutory_rule_repo.refresh(rule_db)

            sentry_logger.info(
                "Statutory rule {rule_id} created by user {user_id}",
                rule_id=rule_db.id,
                user_id=curr_user.id,
            )
            return StatutoryRuleResponse.model_validate(rule_db)
        except EntityExistsError:
            await self._statutory_rule_repo.rollback()
            raise
        except Exception as exc:
            await self._statutory_rule_repo.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while creating statutory rule",
                user_id=curr_user.id,
            )
            raise ServerError() from exc
