# Feishu Messaging API Reference

## Authentication

Feishu API requires App ID and App Secret for tenant access token.

```python
import lark_oapi as lark

client = lark.Client.builder() \
    .app_id("cli_xxx") \
    .app_secret("xxx") \
    .build()
```

## Chat ID Types

| Prefix | Type | receive_id_type |
|--------|------|-----------------|
| `ou_` | User open_id | `open_id` |
| `oc_` | Group chat_id | `chat_id` |
| `on_` | User union_id | `union_id` |
| `om_` | Message ID | - |

## Message Types

### Text Message

```python
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

request = CreateMessageRequest.builder() \
    .receive_id_type("open_id") \
    .request_body(
        CreateMessageRequestBody.builder()
        .receive_id("ou_xxx")
        .msg_type("text")
        .content('{"text":"Hello"}')
        .build()
    ).build()

response = client.im.v1.message.create(request)
```

### Interactive Card

```python
card = {
    "config": {"wide_screen_mode": True},
    "elements": [
        {
            "tag": "div",
            "text": {
                "content": "**Bold** and *italic*",
                "tag": "lark_md"
            }
        }
    ]
}

request = CreateMessageRequest.builder() \
    .receive_id_type("open_id") \
    .request_body(
        CreateMessageRequestBody.builder()
        .receive_id("ou_xxx")
        .msg_type("interactive")
        .content(json.dumps(card))
        .build()
    ).build()
```

### Image Message

```python
from lark_oapi.api.im.v1 import CreateImageRequest, CreateImageRequestBody

# Upload image
with open("image.png", "rb") as f:
    request = CreateImageRequest.builder() \
        .request_body(
            CreateImageRequestBody.builder()
            .image_type("message")
            .image(f)
            .build()
        ).build()
    response = client.im.v1.image.create(request)
    image_key = response.data.image_key

# Send image
request = CreateMessageRequest.builder() \
    .receive_id_type("open_id") \
    .request_body(
        CreateMessageRequestBody.builder()
        .receive_id("ou_xxx")
        .msg_type("image")
        .content(f'{{"image_key":"{image_key}"}}')
        .build()
    ).build()
```

### Audio Message

```python
from lark_oapi.api.im.v1 import CreateFileRequest, CreateFileRequestBody

# Upload audio (must be .opus)
with open("audio.opus", "rb") as f:
    request = CreateFileRequest.builder() \
        .request_body(
            CreateFileRequestBody.builder()
            .file_type("opus")
            .file_name("audio.opus")
            .file(f)
            .build()
        ).build()
    response = client.im.v1.file.create(request)
    file_key = response.data.file_key

# Send audio
request = CreateMessageRequest.builder() \
    .receive_id_type("open_id") \
    .request_body(
        CreateMessageRequestBody.builder()
        .receive_id("ou_xxx")
        .msg_type("audio")
        .content(f'{{"file_key":"{file_key}"}}')
        .build()
    ).build()
```

### File Message

```python
FILE_TYPE_MAP = {
    ".pdf": "pdf", ".doc": "doc", ".docx": "doc",
    ".xls": "xls", ".xlsx": "xls", 
    ".ppt": "ppt", ".pptx": "ppt",
    ".mp4": "mp4", ".opus": "opus",
}

with open("document.pdf", "rb") as f:
    request = CreateFileRequest.builder() \
        .request_body(
            CreateFileRequestBody.builder()
            .file_type("pdf")
            .file_name("document.pdf")
            .file(f)
            .build()
        ).build()
    response = client.im.v1.file.create(request)
    file_key = response.data.file_key

request = CreateMessageRequest.builder() \
    .receive_id_type("open_id") \
    .request_body(
        CreateMessageRequestBody.builder()
        .receive_id("ou_xxx")
        .msg_type("file")
        .content(f'{{"file_key":"{file_key}"}}')
        .build()
    ).build()
```

## Audio Conversion

Feishu only accepts `.opus` format for voice messages.

```bash
# Convert any audio to opus
ffmpeg -i input.mp3 -c:a libopus -b:a 64k output.opus

# Convert with specific sample rate
ffmpeg -i input.wav -c:a libopus -b:a 64k -ar 48000 output.opus

# Batch convert
for f in *.mp3; do
    ffmpeg -i "$f" -c:a libopus -b:a 64k "${f%.mp3}.opus"
done
```

## Error Handling

```python
response = client.im.v1.message.create(request)

if not response.success():
    print(f"Code: {response.code}")
    print(f"Message: {response.msg}")
    print(f"Log ID: {response.get_log_id()}")
```

Common error codes:
- `99991663`: Invalid receive_id
- `99991664`: receive_id_type mismatch
- `99991661`: No permission to send message
- `99991400`: Invalid message content
