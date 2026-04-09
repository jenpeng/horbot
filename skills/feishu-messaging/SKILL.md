---
name: feishu-messaging
version: 1.0.0
description: Send text, images, audio, and files to Feishu/Lark channels. Use when (1) sending messages to Feishu users or groups, (2) uploading and sending media files, (3) working with Feishu chat_id formats (ou_xxx for users, oc_xxx for groups), (4) converting audio to opus format for voice messages.
tags: feishu, lark, messaging, notification, image, audio
always_active: true
---

## When to Use

Use when sending messages to Feishu/Lark channels, uploading media files, or working with Feishu chat IDs.

## Core Rules

### 1. Chat ID Formats

- `ou_xxx` - User open_id (private chat)
- `oc_xxx` - Group chat_id
- Use `receive_id_type="open_id"` for `ou_xxx`
- Use `receive_id_type="chat_id"` for `oc_xxx`

### 2. Message Types

| Type | msg_type | Content Format |
|------|----------|----------------|
| Text Card | `interactive` | `{"config":{"wide_screen_mode":true},"elements":[{"tag":"div","text":{"content":"...","tag":"lark_md"}}]}` |
| Image | `image` | `{"image_key":"img_v3_xxx"}` |
| Audio | `audio` | `{"file_key":"file_v3_xxx"}` (opus only) |
| File | `file` | `{"file_key":"file_v3_xxx"}` |

### 3. Upload Before Send

Media files require two-step process:
1. Upload file → get `image_key` or `file_key`
2. Send message with the key

### 4. Audio Format Requirement

Feishu only accepts `.opus` format for voice messages. Use ffmpeg to convert:

```bash
ffmpeg -i input.mp3 -c:a libopus -b:a 64k output.opus
```

### 5. File Type Mapping

| Extension | file_type |
|-----------|-----------|
| .opus | `opus` |
| .mp4 | `mp4` |
| .pdf | `pdf` |
| .doc | `doc` |
| .docx | `doc` |
| .xls | `xls` |
| .xlsx | `xls` |
| .ppt | `ppt` |
| .pptx | `ppt` |
| Other | `stream` |

## Available Scripts

| Script | Usage |
|--------|-------|
| `scripts/send_message.py` | Send text or card message |
| `scripts/send_image.py` | Upload and send image |
| `scripts/send_audio.py` | Upload and send audio (opus only) |

## Common Traps

- Sending audio in non-opus format will fail
- Forgetting to set correct `receive_id_type` based on chat_id prefix
- Not handling upload failure before attempting to send
- Image upload uses `im.v1.image.create`, file/audio uses `im.v1.file.create`

## API Reference

See [references/api.md](references/api.md) for detailed API documentation.
