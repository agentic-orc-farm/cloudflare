"""The desired shared Access policies, and finding and comparing Access objects. Pure."""

from collections.abc import Iterable

from cf_plane.contract import Refusal

# Names the plane finds Access objects by, not secrets.
SERVICE_TOKEN = "orc-plane-tests"  # noqa: S105
SERVICE_TOKEN_POLICY = "orc-plane-service-token"  # noqa: S105
OWNER_POLICY = "orc-plane-owner"
POLICY_NAMES = (SERVICE_TOKEN_POLICY, OWNER_POLICY)
ONE_TIME_PIN = "onetimepin"


def desired_policies(service_token_id: str, owner_email: str) -> tuple[dict, dict]:
    """The two shared reusable policies: the read-only service token, and the owner by email."""
    return (
        _policy(SERVICE_TOKEN_POLICY, "non_identity", {"service_token": {"token_id": service_token_id}}),
        _policy(OWNER_POLICY, "allow", {"email": {"email": owner_email}}),
    )


def _policy(name: str, decision: str, rule: dict) -> dict:
    return {"name": name, "decision": decision, "include": [rule], "exclude": [], "require": []}


def one_named(items: Iterable[dict], name: str, what: str) -> dict | None:
    """The one item with exactly NAME, None if there is none; two are refused, not repaired."""
    found = [item for item in items if item.get("name") == name]
    if len(found) > 1:
        raise Refusal(
            f"Access: the account has {len(found)} of the {what} {name}; the plane cannot tell which to keep, "
            "so delete the extra one and apply again (docs/cleanup.md, static-site, Access)."
        )
    return found[0] if found else None


def service_token_id(tokens: Iterable[dict]) -> str:
    """The id of the owner's service token `orc-plane-tests`, refused when it is missing or doubled."""
    found = [token for token in tokens if token.get("name") == SERVICE_TOKEN]
    if len(found) != 1:
        raise Refusal(
            f"Access: the account has {len(found)} service tokens named {SERVICE_TOKEN}, not exactly one; "
            "the owner makes it once (README, owner set-up step 3)."
        )
    return str(found[0]["id"])


def one_time_pin_id(providers: Iterable[dict]) -> str:
    """The id of the account's one-time PIN login method, refused when it is missing or doubled."""
    found = [provider for provider in providers if provider.get("type") == ONE_TIME_PIN]
    if len(found) != 1:
        raise Refusal(
            f"Access: the account has {len(found)} one-time PIN login methods, not exactly one; "
            "the owner adds it once (README, owner set-up step 2)."
        )
    return str(found[0]["id"])


def policy_matches(observed: dict, desired: dict) -> bool:
    """Whether a reusable policy has the desired decision and exactly the desired rules."""
    return observed.get("decision") == desired["decision"] and all(
        _rules(observed.get(key)) == _rules(desired[key]) for key in ("include", "exclude", "require")
    )


def _rules(rules: list | None) -> list:
    return sorted((_normalised(rule) for rule in rules or []), key=repr)


def _normalised(rule: dict) -> dict:
    if "email" in rule and isinstance(rule["email"], dict):
        return {"email": {"email": str(rule["email"].get("email", "")).lower()}}
    return rule


def apps_for_worker(apps: Iterable[dict], worker_ids: frozenset[str]) -> list[dict]:
    """The applications with a `worker` destination for any of the Worker's ids."""
    return [
        app
        for app in apps
        if any(
            destination.get("type") == "worker" and destination.get("worker_id") in worker_ids
            for destination in app.get("destinations") or []
        )
    ]


def app_matches(observed: dict, desired: dict, worker_ids: frozenset[str]) -> bool:
    """Whether an application has every field the plane sets as desired.

    A flag the API leaves out of its response cannot be compared, so it is taken as matching.
    """
    destinations = observed.get("destinations") or []
    policies = sorted(observed.get("policies") or [], key=lambda policy: policy.get("precedence") or 0)
    return (
        observed.get("type") == desired["type"]
        and observed.get("name") == desired["name"]
        and len(destinations) == 1
        and destinations[0].get("type") == "worker"
        and destinations[0].get("worker_id") in worker_ids
        and [(policy.get("id"), policy.get("precedence")) for policy in policies]
        == [(policy["id"], policy["precedence"]) for policy in desired["policies"]]
        and list(observed.get("allowed_idps") or []) == desired["allowed_idps"]
        and observed.get("auto_redirect_to_identity", desired["auto_redirect_to_identity"])
        == desired["auto_redirect_to_identity"]
        and observed.get("app_launcher_visible", desired["app_launcher_visible"]) == desired["app_launcher_visible"]
    )
