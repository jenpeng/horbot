#!/usr/bin/env python3
"""Send message to Feishu channel.

Usage:
    python send_message.py <chat_id> <content> [--card]

Arguments:
    chat_id: Feishu chat ID (ou_xxx for user, oc_xxx for group)
    content: Message content (text or markdown)

Options:
    --card: Send as interactive card (default: plain text)
"""
import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
    FEISHU_AVAILABLE = True
except ImportError:
    FEISHU_AVAILABLE = False


def send_text_message(client, chat_id: str, content: str) -> bool:
    """Send plain text message."""
    receive_id_type = "open_id" if chat_id.startswith("ou_") else "chat_id"
    
    request = CreateMessageRequest.builder() \
        .receive_id_type(receive_id_type) \
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("text")
            .content(json.dumps({"text": content}, ensure_ascii=False))
            .build()
        ).build()
    
    response = client.im.v1.message.create(request)
    return response.success()


def send_card_message(client, chat_id: str, content: str) -> bool:
    """Send interactive card message with markdown support."""
    receive_id_type = "open_id" if chat_id.startswith("ou_") else "chat_id"
    
    card = {
        "config": {"wide_screen_mode": True},
        "elements": [
            {
                "tag": "div",
                "text": {
                    "content": content,
                    "tag": "lark_md"
                }
            }
        ]
    }
    
    request = CreateMessageRequest.builder() \
        .receive_id_type(receive_id_type) \
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("interactive")
            .content(json.dumps(card, ensure_ascii=False))
            .build()
        ).build()
    
    response = client.im.v1.message.create(request)
    return response.success()


def main():
    if not FEISHU_AVAILABLE:
        print("Error: lark-oapi not installed. Run: pip install lark-oapi")
        sys.exit(1)
    
    parser = argparse.ArgumentParser(description="Send message to Feishu")
    parser.add_argument("chat_id", help="Feishu chat ID (ou_xxx or oc_xxx)")
    parser.add_argument("content", help="Message content")
    parser.add_argument("--card", action="store_true", help="Send as interactive card")
    args = parser.parse_args()
    
    from horbot.config.loader import get_cached_config
    config = get_cached_config()
    feishu_config = config.channels.feishu
    
    if not feishu_config.app_id or not feishu_config.app_secret:
        print("Error: Feishu not configured. Set app_id and app_secret in config.")
        sys.exit(1)
    
    client = lark.Client.builder() \
        .app_id(feishu_config.app_id) \
        .app_secret(feishu_config.app_secret) \
        .log_level(lark.LogLevel.ERROR) \
        .build()
    
    if args.card:
        success = send_card_message(client, args.chat_id, args.content)
    else:
        success = send_text_message(client, args.chat_id, args.content)
    
    if success:
        print(f"Message sent to {args.chat_id}")
    else:
        print(f"Failed to send message")
        sys.exit(1)


if __name__ == "__main__":
    main()
