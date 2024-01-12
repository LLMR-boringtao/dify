import os
from typing import Optional

from flask import Flask
from pydantic import BaseModel

from core.entities.provider_entities import QuotaUnit, RestrictModel
from core.model_runtime.entities.model_entities import ModelType
from models.provider import ProviderQuotaType


class HostingQuota(BaseModel):
    quota_type: ProviderQuotaType
    restrict_models: list[RestrictModel] = []


class TrialHostingQuota(HostingQuota):
    quota_type: ProviderQuotaType = ProviderQuotaType.TRIAL
    quota_limit: int = 0
    """Quota limit for the hosting provider models. -1 means unlimited."""


class PaidHostingQuota(HostingQuota):
    quota_type: ProviderQuotaType = ProviderQuotaType.PAID
    stripe_price_id: str = None
    increase_quota: int = 1
    min_quantity: int = 20
    max_quantity: int = 100


class FreeHostingQuota(HostingQuota):
    quota_type: ProviderQuotaType = ProviderQuotaType.FREE


class HostingProvider(BaseModel):
    enabled: bool = False
    credentials: Optional[dict] = None
    quota_unit: Optional[QuotaUnit] = None
    quotas: list[HostingQuota] = []


class HostedModerationConfig(BaseModel):
    enabled: bool = False
    providers: list[str] = []


class HostingConfiguration:
    provider_map: dict[str, HostingProvider] = {}
    moderation_config: HostedModerationConfig = None

    def init_app(self, app: Flask) -> None:
        if app.config.get('EDITION') != 'CLOUD':
            return

        self.provider_map["azure_openai"] = self.init_azure_openai()
        self.provider_map["openai"] = self.init_openai()
        self.provider_map["anthropic"] = self.init_anthropic()
        self.provider_map["minimax"] = self.init_minimax()
        self.provider_map["spark"] = self.init_spark()
        self.provider_map["zhipuai"] = self.init_zhipuai()

        self.moderation_config = self.init_moderation_config()

    def init_azure_openai(self) -> HostingProvider:
        quota_unit = QuotaUnit.TIMES
        if os.environ.get("HOSTED_AZURE_OPENAI_ENABLED") and os.environ.get("HOSTED_AZURE_OPENAI_ENABLED").lower() == 'true':
            credentials = {
                "openai_api_key": os.environ.get("HOSTED_AZURE_OPENAI_API_KEY"),
                "openai_api_base": os.environ.get("HOSTED_AZURE_OPENAI_API_BASE"),
                "base_model_name": "gpt-35-turbo"
            }

            quotas = []
            hosted_quota_limit = int(os.environ.get("HOSTED_AZURE_OPENAI_QUOTA_LIMIT", "1000"))
            if hosted_quota_limit != -1 or hosted_quota_limit > 0:
                trial_quota = TrialHostingQuota(
                    quota_limit=hosted_quota_limit,
                    restrict_models=[
                        RestrictModel(model="gpt-4", base_model_name="gpt-4", model_type=ModelType.LLM),
                        RestrictModel(model="gpt-4-32k", base_model_name="gpt-4-32k", model_type=ModelType.LLM),
                        RestrictModel(model="gpt-4-1106-preview", base_model_name="gpt-4-1106-preview", model_type=ModelType.LLM),
                        RestrictModel(model="gpt-4-vision-preview", base_model_name="gpt-4-vision-preview", model_type=ModelType.LLM),
                        RestrictModel(model="gpt-35-turbo", base_model_name="gpt-35-turbo", model_type=ModelType.LLM),
                        RestrictModel(model="gpt-35-turbo-1106", base_model_name="gpt-35-turbo-1106", model_type=ModelType.LLM),
                        RestrictModel(model="gpt-35-turbo-instruct", base_model_name="gpt-35-turbo-instruct", model_type=ModelType.LLM),
                        RestrictModel(model="gpt-35-turbo-16k", base_model_name="gpt-35-turbo-16k", model_type=ModelType.LLM),
                        RestrictModel(model="text-davinci-003", base_model_name="text-davinci-003", model_type=ModelType.LLM),
                        RestrictModel(model="text-embedding-ada-002", base_model_name="text-embedding-ada-002", model_type=ModelType.TEXT_EMBEDDING),
                    ]
                )
                quotas.append(trial_quota)

            return HostingProvider(
                enabled=True,
                credentials=credentials,
                quota_unit=quota_unit,
                quotas=quotas
            )

        return HostingProvider(
            enabled=False,
            quota_unit=quota_unit,
        )

    def init_openai(self) -> HostingProvider:
        quota_unit = QuotaUnit.TIMES
        if os.environ.get("HOSTED_OPENAI_ENABLED") and os.environ.get("HOSTED_OPENAI_ENABLED").lower() == 'true':
            credentials = {
                "openai_api_key": os.environ.get("HOSTED_OPENAI_API_KEY"),
            }

            if os.environ.get("HOSTED_OPENAI_API_BASE"):
                credentials["openai_api_base"] = os.environ.get("HOSTED_OPENAI_API_BASE")

            if os.environ.get("HOSTED_OPENAI_API_ORGANIZATION"):
                credentials["openai_organization"] = os.environ.get("HOSTED_OPENAI_API_ORGANIZATION")

            quotas = []
            hosted_quota_limit = int(os.environ.get("HOSTED_OPENAI_QUOTA_LIMIT", "200"))
            if hosted_quota_limit != -1 or hosted_quota_limit > 0:
                trial_quota = TrialHostingQuota(
                    quota_limit=hosted_quota_limit,
                    restrict_models=[
                        RestrictModel(model="gpt-3.5-turbo", model_type=ModelType.LLM),
                        RestrictModel(model="gpt-3.5-turbo-1106", model_type=ModelType.LLM),
                        RestrictModel(model="gpt-3.5-turbo-instruct", model_type=ModelType.LLM),
                        RestrictModel(model="gpt-3.5-turbo-16k", model_type=ModelType.LLM),
                        RestrictModel(model="text-davinci-003", model_type=ModelType.LLM),
                    ]
                )
                quotas.append(trial_quota)

            if os.environ.get("HOSTED_OPENAI_PAID_ENABLED") and os.environ.get(
                    "HOSTED_OPENAI_PAID_ENABLED").lower() == 'true':
                paid_quota = PaidHostingQuota(
                    stripe_price_id=os.environ.get("HOSTED_OPENAI_PAID_STRIPE_PRICE_ID"),
                    increase_quota=int(os.environ.get("HOSTED_OPENAI_PAID_INCREASE_QUOTA", "1")),
                    min_quantity=int(os.environ.get("HOSTED_OPENAI_PAID_MIN_QUANTITY", "1")),
                    max_quantity=int(os.environ.get("HOSTED_OPENAI_PAID_MAX_QUANTITY", "1"))
                )
                quotas.append(paid_quota)

            return HostingProvider(
                enabled=True,
                credentials=credentials,
                quota_unit=quota_unit,
                quotas=quotas
            )

        return HostingProvider(
            enabled=False,
            quota_unit=quota_unit,
        )

    def init_anthropic(self) -> HostingProvider:
        quota_unit = QuotaUnit.TOKENS
        if os.environ.get("HOSTED_ANTHROPIC_ENABLED") and os.environ.get("HOSTED_ANTHROPIC_ENABLED").lower() == 'true':
            credentials = {
                "anthropic_api_key": os.environ.get("HOSTED_ANTHROPIC_API_KEY"),
            }

            if os.environ.get("HOSTED_ANTHROPIC_API_BASE"):
                credentials["anthropic_api_url"] = os.environ.get("HOSTED_ANTHROPIC_API_BASE")

            quotas = []
            hosted_quota_limit = int(os.environ.get("HOSTED_ANTHROPIC_QUOTA_LIMIT", "0"))
            if hosted_quota_limit != -1 or hosted_quota_limit > 0:
                trial_quota = TrialHostingQuota(
                    quota_limit=hosted_quota_limit
                )
                quotas.append(trial_quota)

            if os.environ.get("HOSTED_ANTHROPIC_PAID_ENABLED") and os.environ.get(
                    "HOSTED_ANTHROPIC_PAID_ENABLED").lower() == 'true':
                paid_quota = PaidHostingQuota(
                    stripe_price_id=os.environ.get("HOSTED_ANTHROPIC_PAID_STRIPE_PRICE_ID"),
                    increase_quota=int(os.environ.get("HOSTED_ANTHROPIC_PAID_INCREASE_QUOTA", "1000000")),
                    min_quantity=int(os.environ.get("HOSTED_ANTHROPIC_PAID_MIN_QUANTITY", "20")),
                    max_quantity=int(os.environ.get("HOSTED_ANTHROPIC_PAID_MAX_QUANTITY", "100"))
                )
                quotas.append(paid_quota)

            return HostingProvider(
                enabled=True,
                credentials=credentials,
                quota_unit=quota_unit,
                quotas=quotas
            )

        return HostingProvider(
            enabled=False,
            quota_unit=quota_unit,
        )

    def init_minimax(self) -> HostingProvider:
        quota_unit = QuotaUnit.TOKENS
        if os.environ.get("HOSTED_MINIMAX_ENABLED") and os.environ.get("HOSTED_MINIMAX_ENABLED").lower() == 'true':
            quotas = [FreeHostingQuota()]

            return HostingProvider(
                enabled=True,
                credentials=None,  # use credentials from the provider
                quota_unit=quota_unit,
                quotas=quotas
            )

        return HostingProvider(
            enabled=False,
            quota_unit=quota_unit,
        )

    def init_spark(self) -> HostingProvider:
        quota_unit = QuotaUnit.TOKENS
        if os.environ.get("HOSTED_SPARK_ENABLED") and os.environ.get("HOSTED_SPARK_ENABLED").lower() == 'true':
            quotas = [FreeHostingQuota()]

            return HostingProvider(
                enabled=True,
                credentials=None,  # use credentials from the provider
                quota_unit=quota_unit,
                quotas=quotas
            )

        return HostingProvider(
            enabled=False,
            quota_unit=quota_unit,
        )

    def init_zhipuai(self) -> HostingProvider:
        quota_unit = QuotaUnit.TOKENS
        if os.environ.get("HOSTED_ZHIPUAI_ENABLED") and os.environ.get("HOSTED_ZHIPUAI_ENABLED").lower() == 'true':
            quotas = [FreeHostingQuota()]

            return HostingProvider(
                enabled=True,
                credentials=None,  # use credentials from the provider
                quota_unit=quota_unit,
                quotas=quotas
            )

        return HostingProvider(
            enabled=False,
            quota_unit=quota_unit,
        )

    def init_moderation_config(self) -> HostedModerationConfig:
        if os.environ.get("HOSTED_MODERATION_ENABLED") and os.environ.get("HOSTED_MODERATION_ENABLED").lower() == 'true' \
                and os.environ.get("HOSTED_MODERATION_PROVIDERS"):
            return HostedModerationConfig(
                enabled=True,
                providers=os.environ.get("HOSTED_MODERATION_PROVIDERS").split(',')
            )

        return HostedModerationConfig(
            enabled=False
        )