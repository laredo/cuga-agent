"""PersonalConfig — reads from CUGA's Dynaconf settings under [personal]."""
from typing import List
from dataclasses import dataclass, field


@dataclass
class SlackConfig:
    enabled: bool = False
    bot_token: str = ""
    app_token: str = ""
    signing_secret: str = ""
    default_channel: str = ""


@dataclass
class EmailConfig:
    enabled: bool = False
    imap_server: str = ""
    smtp_server: str = ""
    email_address: str = ""


@dataclass
class SchedulerConfig:
    enabled: bool = True
    check_interval: int = 30
    max_concurrent_jobs: int = 5


@dataclass
class ModelRoutingConfig:
    enabled: bool = False
    cheap_model: str = ""
    expensive_model: str = ""


@dataclass
class PersonalConfig:
    enabled: bool = False
    skill_dirs: List[str] = field(default_factory=lambda: ["~/.cuga/skills/", "./skills/"])
    default_channel: str = "cli"
    slack: SlackConfig = field(default_factory=SlackConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    model_routing: ModelRoutingConfig = field(default_factory=ModelRoutingConfig)

    @classmethod
    def from_settings(cls) -> "PersonalConfig":
        """Load PersonalConfig from CUGA's Dynaconf settings."""
        try:
            from cuga.config import settings

            p = settings.get("personal", {})
            if not p:
                return cls()

            def _sub(key, klass):
                sub = p.get(key, {})
                if isinstance(sub, dict):
                    return klass(**{k: v for k, v in sub.items() if k in klass.__dataclass_fields__})
                return klass()

            return cls(
                enabled=p.get("enabled", False),
                skill_dirs=p.get("skill_dirs", ["~/.cuga/skills/", "./skills/"]),
                default_channel=p.get("default_channel", "cli"),
                slack=_sub("slack", SlackConfig),
                email=_sub("email", EmailConfig),
                scheduler=_sub("scheduler", SchedulerConfig),
                model_routing=_sub("model_routing", ModelRoutingConfig),
            )
        except Exception:
            return cls()
