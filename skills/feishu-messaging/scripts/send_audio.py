#!/usr/bin/env python3
"""Send audio message to Feishu channel.

Usage:
    python send_audio.py <chat_id> <audio_path>

Arguments:
    chat_id: Feishu chat ID (ou_xxx for user, oc_xxx for group)
    audio_path: Path to audio file (must be .opus format)

Note:
    Feishu only supports .opus format for voice messages.
    Use ffmpeg to convert other formats:
        ffmpeg -i input.mp3 -c:a libopus -b:a 64k output.opus
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
        CreateFileRequest,
        CreateFileRequestBody,
    )
    FEISHU_AVAILABLE = True
except ImportError:
    FEISHU_AVAILABLE = False

FILE_TYPE_MAP = {
    ".opus": "opus", ".mp4": "mp4", ".pdf": "pdf", 
    ".doc": "doc", ".docx": "doc",
    ".xls": "xls", ".xlsx": "xls", 
    ".ppt": "ppt", ".pptx": "ppt",
}


def send_audio(client, chat_id: str, audio_path: str) -> bool:
    """Upload and send audio to Feishu."""
    if not os.path.exists(audio_path):
        print(f"Error: Audio file not found: {audio_path}")
        return False
    
    ext = os.path.splitext(audio_path)[1].lower()
    if ext != ".opus":
        print(f"Error: Feishu only supports .opus format, got: {ext}")
        print("Convert with: ffmpeg -i input.mp3 -c:a libopus -b:a 64k output.opus")
        return False
    
    receive_id_type = "open_id" if chat_id.startswith("ou_") else "chat_id"
    file_name = os.path.basename(audio_path)
    
    with open(audio_path, "rb") as f:
        request = CreateFileRequest.builder() \
            .request_body(
                CreateFileRequestBody.builder()
                .file_type("opus")
                .file_name(file_name)
                .file(f)
                .build()
            ).build()
        response = client.im.v1.file.create(request)
        
        if not response.success():
            print(f"Error: Failed to upload audio: {response.code} - {response.msg}")
            return False
        
        file_key = response.data.file_key
    
    content = json.dumps({"file_key": file_key})
    
    request = CreateMessageRequest.builder() \
        .receive_id_type(receive_id_type) \
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("audio")
            .content(content)
            .build()
        ).build()
    
    response = client.im.v1.message.create(request)
    return response.success()


def main():
    if not FEISHU_AVAILABLE:
        print("Error: lark-oapi not installed. Run: pip install lark-oapi")
        sys.exit(1)
    
    parser = argparse.ArgumentParser(description="Send audio to Feishu")
    parser.add_argument("chat_id", help="Feishu chat ID (ou_xxx or oc_xxx)")
    parser.add_argument("audio_path", help="Path to .opus audio file")
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
    
    if send_audio(client, args.chat_id, args.audio_path):
        print(f"Audio sent to {args.chat_id}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
