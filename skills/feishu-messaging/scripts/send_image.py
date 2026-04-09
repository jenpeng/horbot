#!/usr/bin/env python3
"""Send image to Feishu channel.

Usage:
    python send_image.py <chat_id> <image_path>

Arguments:
    chat_id: Feishu chat ID (ou_xxx for user, oc_xxx for group)
    image_path: Path to image file (png, jpg, gif, etc.)
"""
import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import (
        CreateMessageRequest, 
        CreateMessageRequestBody,
        CreateImageRequest,
        CreateImageRequestBody,
    )
    FEISHU_AVAILABLE = True
except ImportError:
    FEISHU_AVAILABLE = False

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".tiff", ".tif"}


def send_image(client, chat_id: str, image_path: str) -> bool:
    """Upload and send image to Feishu."""
    if not os.path.exists(image_path):
        print(f"Error: Image file not found: {image_path}")
        return False
    
    ext = os.path.splitext(image_path)[1].lower()
    if ext not in IMAGE_EXTS:
        print(f"Error: Unsupported image format: {ext}")
        print(f"Supported formats: {', '.join(IMAGE_EXTS)}")
        return False
    
    receive_id_type = "open_id" if chat_id.startswith("ou_") else "chat_id"
    
    with open(image_path, "rb") as f:
        request = CreateImageRequest.builder() \
            .request_body(
                CreateImageRequestBody.builder()
                .image_type("message")
                .image(f)
                .build()
            ).build()
        response = client.im.v1.image.create(request)
        
        if not response.success():
            print(f"Error: Failed to upload image: {response.code} - {response.msg}")
            return False
        
        image_key = response.data.image_key
    
    content = json.dumps({"image_key": image_key})
    
    request = CreateMessageRequest.builder() \
        .receive_id_type(receive_id_type) \
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("image")
            .content(content)
            .build()
        ).build()
    
    response = client.im.v1.message.create(request)
    return response.success()


def main():
    if not FEISHU_AVAILABLE:
        print("Error: lark-oapi not installed. Run: pip install lark-oapi")
        sys.exit(1)
    
    parser = argparse.ArgumentParser(description="Send image to Feishu")
    parser.add_argument("chat_id", help="Feishu chat ID (ou_xxx or oc_xxx)")
    parser.add_argument("image_path", help="Path to image file")
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
    
    if send_image(client, args.chat_id, args.image_path):
        print(f"Image sent to {args.chat_id}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
