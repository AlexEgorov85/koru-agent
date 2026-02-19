#!/usr/bin/env python3
"""
CLI-СѓС‚РёР»РёС‚Р° РґР»СЏ СѓРїСЂР°РІР»РµРЅРёСЏ РїСЂРѕРјРїС‚Р°РјРё
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone
import json

# Р”РѕР±Р°РІР»СЏРµРј РїСѓС‚СЊ Рє РєРѕСЂРЅСЋ РїСЂРѕРµРєС‚Р° РґР»СЏ РёРјРїРѕСЂС‚Р° РјРѕРґСѓР»РµР№
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models.data.prompt import Prompt, PromptStatus, PromptMetadata
from core.models.data.prompt_serialization import PromptSerializer
from core.infrastructure.registry.prompt_registry import PromptRegistry


def create_prompt(args):
    """РЎРѕР·РґР°РµС‚ РЅРѕРІС‹Р№ РїСЂРѕРјРїС‚-С‡РµСЂРЅРѕРІРёРє"""
    print(f"РЎРѕР·РґР°РЅРёРµ РЅРѕРІРѕРіРѕ РїСЂРѕРјРїС‚Р°: {args.capability} РІРµСЂСЃРёРё {args.version}")
    
    # РћРїСЂРµРґРµР»СЏРµРј С€Р°Р±Р»РѕРЅ СЃРѕРґРµСЂР¶РёРјРѕРіРѕ
    content_templates = {
        "planning": """# РџР»Р°РЅРёСЂРѕРІР°РЅРёРµ Р·Р°РґР°С‡Рё

Р’С‹ - РїРѕРјРѕС‰РЅРёРє РїРѕ РїР»Р°РЅРёСЂРѕРІР°РЅРёСЋ Р·Р°РґР°С‡. Р’Р°С€Р° С†РµР»СЊ - РїРѕРјРѕС‡СЊ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ СЂР°Р·Р±РёС‚СЊ СЃР»РѕР¶РЅСѓСЋ Р·Р°РґР°С‡Сѓ РЅР° РїРѕРґР·Р°РґР°С‡Рё.

## РљРѕРЅС‚РµРєСЃС‚:
{{ context }}

## Р—Р°РґР°С‡Р°:
{{ task }}

## РўСЂРµР±РѕРІР°РЅРёСЏ:
{{ requirements }}

## Р РµР·СѓР»СЊС‚Р°С‚:
""",
        "analysis": """# РђРЅР°Р»РёР· РёРЅС„РѕСЂРјР°С†РёРё

Р’С‹ - Р°РЅР°Р»РёС‚РёС‡РµСЃРєРёР№ РїРѕРјРѕС‰РЅРёРє. Р’Р°С€Р° С†РµР»СЊ - РїСЂРѕР°РЅР°Р»РёР·РёСЂРѕРІР°С‚СЊ РїСЂРµРґРѕСЃС‚Р°РІР»РµРЅРЅСѓСЋ РёРЅС„РѕСЂРјР°С†РёСЋ Рё РїСЂРµРґРѕСЃС‚Р°РІРёС‚СЊ СЃС‚СЂСѓРєС‚СѓСЂРёСЂРѕРІР°РЅРЅС‹Р№ РѕР±Р·РѕСЂ.

## Р”Р°РЅРЅС‹Рµ РґР»СЏ Р°РЅР°Р»РёР·Р°:
{{ data }}

## РљСЂРёС‚РµСЂРёРё Р°РЅР°Р»РёР·Р°:
{{ criteria }}

## Р РµР·СѓР»СЊС‚Р°С‚ Р°РЅР°Р»РёР·Р°:
""",
        "default": """# {{ title }}

{{ description }}

## Р’С…РѕРґРЅС‹Рµ РґР°РЅРЅС‹Рµ:
{% for var in input_vars %}
- {{ var }}
{% endfor %}

## Р РµР·СѓР»СЊС‚Р°С‚:
"""
    }
    
    template = content_templates.get(args.template, content_templates["default"])
    
    # РЎРѕР·РґР°РµРј РјРµС‚Р°РґР°РЅРЅС‹Рµ
    metadata = PromptMetadata(
        version=args.version,
        skill=args.capability.split('.')[0] if '.' in args.capability else 'general',
        capability=args.capability,
        role="system",
        language="ru",
        tags=[args.template] if args.template else ["general"],
        variables=["title", "description", "input_vars"] if args.template == "default" else [],
        status=PromptStatus.DRAFT,
        quality_metrics={},
        author=args.author,
        changelog=[f"РЎРѕР·РґР°РЅ {datetime.now(timezone.utc).isoformat()}"]
    )
    
    # РЎРѕР·РґР°РµРј РїСЂРѕРјРїС‚
    prompt = Prompt(
        metadata=metadata,
        content=template
    )
    
    # РЎРѕС…СЂР°РЅСЏРµРј РїСЂРѕРјРїС‚
    base_path = Path("prompts")
    file_path = PromptSerializer.to_file(prompt, base_path)
    
    print(f"РџСЂРѕРјРїС‚ СЃРѕР·РґР°РЅ: {file_path}")
    return True


def promote_prompt(args):
    """РџСЂРѕРјРѕСѓС‚РёС‚ РїСЂРѕРјРїС‚ РІ Р°РєС‚РёРІРЅС‹Р№ СЃС‚Р°С‚СѓСЃ"""
    print(f"РџСЂРѕРґРІРёР¶РµРЅРёРµ РїСЂРѕРјРїС‚Р°: {args.capability} РІРµСЂСЃРёРё {args.version}")
    
    # Р—Р°РіСЂСѓР¶Р°РµРј РїСЂРѕРјРїС‚
    registry = PromptRegistry(Path("prompts") / "registry.yaml")
    prompt = registry.get_prompt_by_capability_and_version(args.capability, args.version)
    
    if not prompt:
        print(f"РћС€РёР±РєР°: РџСЂРѕРјРїС‚ {args.capability} РІРµСЂСЃРёРё {args.version} РЅРµ РЅР°Р№РґРµРЅ")
        return False
    
    # РћР±РЅРѕРІР»СЏРµРј СЃС‚Р°С‚СѓСЃ
    prompt.metadata.status = PromptStatus.ACTIVE
    prompt.metadata.updated_at = datetime.now(timezone.utc)
    prompt.metadata.changelog.append(f"РџСЂРѕРґРІРёРЅСѓС‚ РІ Р°РєС‚РёРІРЅС‹Рµ {datetime.now(timezone.utc).isoformat()}")
    
    # РћР±РЅРѕРІР»СЏРµРј СЂРµРµСЃС‚СЂ
    success = registry.promote(prompt)
    
    if success:
        print(f"РџСЂРѕРјРїС‚ {args.capability} РІРµСЂСЃРёРё {args.version} СѓСЃРїРµС€РЅРѕ РїСЂРѕРґРІРёРЅСѓС‚ РІ Р°РєС‚РёРІРЅС‹Рµ")
    else:
        print(f"РћС€РёР±РєР° РїСЂРё РїСЂРѕРґРІРёР¶РµРЅРёРё РїСЂРѕРјРїС‚Р° {args.capability} РІРµСЂСЃРёРё {args.version}")
    
    return success


def archive_prompt(args):
    """РђСЂС…РёРІРёСЂСѓРµС‚ РїСЂРѕРјРїС‚"""
    print(f"РђСЂС…РёРІР°С†РёСЏ РїСЂРѕРјРїС‚Р°: {args.capability} РІРµСЂСЃРёРё {args.version}")
    
    # Р—Р°РіСЂСѓР¶Р°РµРј СЂРµРµСЃС‚СЂ
    registry = PromptRegistry(Path("prompts") / "registry.yaml")
    
    # РђСЂС…РёРІРёСЂСѓРµРј РїСЂРѕРјРїС‚
    success = registry.archive(args.capability, args.version, args.reason)
    
    if success:
        print(f"РџСЂРѕРјРїС‚ {args.capability} РІРµСЂСЃРёРё {args.version} СѓСЃРїРµС€РЅРѕ Р°СЂС…РёРІРёСЂРѕРІР°РЅ")
    else:
        print(f"РћС€РёР±РєР° РїСЂРё Р°СЂС…РёРІР°С†РёРё РїСЂРѕРјРїС‚Р° {args.capability} РІРµСЂСЃРёРё {args.version}")
    
    return success


def show_status(args):
    """РџРѕРєР°Р·С‹РІР°РµС‚ СЃС‚Р°С‚СѓСЃ РІСЃРµС… РїСЂРѕРјРїС‚РѕРІ"""
    print("РЎС‚Р°С‚СѓСЃ РїСЂРѕРјРїС‚РѕРІ:")
    
    # Р—Р°РіСЂСѓР¶Р°РµРј СЂРµРµСЃС‚СЂ
    registry = PromptRegistry(Path("prompts") / "registry.yaml")
    
    print("\nРђРєС‚РёРІРЅС‹Рµ РїСЂРѕРјРїС‚С‹:")
    for capability, entry in registry.active_prompts.items():
        print(f"  - {capability}: {entry.version} ({entry.status.value}) - {entry.file_path}")
    
    print("\nРђСЂС…РёРІРЅС‹Рµ РїСЂРѕРјРїС‚С‹:")
    for (capability, version), entry in registry.archived_prompts.items():
        print(f"  - {capability}: {version} ({entry.status.value}) - {entry.file_path}")


def main():
    parser = argparse.ArgumentParser(description="CLI-СѓС‚РёР»РёС‚Р° РґР»СЏ СѓРїСЂР°РІР»РµРЅРёСЏ РїСЂРѕРјРїС‚Р°РјРё")
    subparsers = parser.add_subparsers(dest="command", help="Р”РѕСЃС‚СѓРїРЅС‹Рµ РєРѕРјР°РЅРґС‹")
    
    # РљРѕРјР°РЅРґР° create
    create_parser = subparsers.add_parser("create", help="РЎРѕР·РґР°С‚СЊ РЅРѕРІС‹Р№ РїСЂРѕРјРїС‚-С‡РµСЂРЅРѕРІРёРє")
    create_parser.add_argument("--capability", required=True, help="РќР°Р·РІР°РЅРёРµ РІРѕР·РјРѕР¶РЅРѕСЃС‚Рё (РЅР°РїСЂРёРјРµСЂ, planning.create_plan)")
    create_parser.add_argument("--version", required=True, help="Р’РµСЂСЃРёСЏ РїСЂРѕРјРїС‚Р° (РЅР°РїСЂРёРјРµСЂ, v1.0.0)")
    create_parser.add_argument("--template", default="default", choices=["planning", "analysis", "default"], help="РЁР°Р±Р»РѕРЅ РґР»СЏ РїСЂРѕРјРїС‚Р°")
    create_parser.add_argument("--author", required=True, help="РђРІС‚РѕСЂ РїСЂРѕРјРїС‚Р°")
    
    # РљРѕРјР°РЅРґР° promote
    promote_parser = subparsers.add_parser("promote", help="РџСЂРѕРґРІРёРЅСѓС‚СЊ РїСЂРѕРјРїС‚ РІ Р°РєС‚РёРІРЅС‹Р№ СЃС‚Р°С‚СѓСЃ")
    promote_parser.add_argument("--capability", required=True, help="РќР°Р·РІР°РЅРёРµ РІРѕР·РјРѕР¶РЅРѕСЃС‚Рё")
    promote_parser.add_argument("--version", required=True, help="Р’РµСЂСЃРёСЏ РїСЂРѕРјРїС‚Р°")
    
    # РљРѕРјР°РЅРґР° archive
    archive_parser = subparsers.add_parser("archive", help="РђСЂС…РёРІРёСЂРѕРІР°С‚СЊ РїСЂРѕРјРїС‚")
    archive_parser.add_argument("--capability", required=True, help="РќР°Р·РІР°РЅРёРµ РІРѕР·РјРѕР¶РЅРѕСЃС‚Рё")
    archive_parser.add_argument("--version", required=True, help="Р’РµСЂСЃРёСЏ РїСЂРѕРјРїС‚Р°")
    archive_parser.add_argument("--reason", default="", help="РџСЂРёС‡РёРЅР° Р°СЂС…РёРІР°С†РёРё")
    
    # РљРѕРјР°РЅРґР° status
    status_parser = subparsers.add_parser("status", help="РџРѕРєР°Р·Р°С‚СЊ СЃС‚Р°С‚СѓСЃ РІСЃРµС… РїСЂРѕРјРїС‚РѕРІ")
    
    args = parser.parse_args()
    
    if args.command == "create":
        success = create_prompt(args)
    elif args.command == "promote":
        success = promote_prompt(args)
    elif args.command == "archive":
        success = archive_prompt(args)
    elif args.command == "status":
        show_status(args)
    else:
        parser.print_help()
        sys.exit(1)
    
    if not success and args.command in ["create", "promote", "archive"]:
        sys.exit(1)


if __name__ == "__main__":
    main()